import requests
import json
import logging
import time
from bs4 import BeautifulSoup
import os
import matplotlib.pyplot as plt
import argparse
from datetime import datetime

USER_LIST_FILE_NAME = "users.json"
USER_MONSTERS_FILE = "monsters.json"
REQUEST_DELAY = 1

# Minimal logging setup
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def start_session():
    """
    Starts a requests.Session and logs into the website using credentials
    from the 'input.json' file.
    
    Returns:
        session (requests.Session): Authenticated session object on success.
    
    Raises:
        FileNotFoundError: If the 'input.json' file does not exist.
        KeyError: If expected credentials keys are missing in the JSON.
        Exception: For any login failure (non-200 status code) during the POST request.
    """
    # Read credentials from input.json
    try:
        with open("input.json", "r") as file:
            credentials = json.load(file)
            login = credentials["login"]
            password = credentials["password"]
    except FileNotFoundError:
        logger.error("The file 'input.json' was not found.")
        raise
    except KeyError as e:
        logger.error("Missing key in 'input.json': %s", e)
        raise

    # Create a session
    session = requests.Session()

    # Define the login URL and POST data
    login_url = "https://www.metamob.fr/connexion"
    payload = {
        "identifiant": login,
        "password": password
    }

    # Perform the login POST request
    try:
        response = session.post(login_url, data=payload)
    except Exception as e:
        logger.error("An error occurred during the POST request: %s", e)
        raise

    # Check if the login was successful based on the response code.
    if response.status_code == 200:
        logger.info("Successfully logged in to %s", login_url)
        if "Identifiants incorrects" in response.text:
            raise Exception("Login failed. Check your credentials.")
    else:
        logger.error("Login failed with status code %s. Response: %s", response.status_code, response.text)
        raise Exception("Login failed. Check your credentials and the website.")

    return session

def fetch_users_page(session):
    """
    Uses an authenticated session to GET the user list page and returns its HTML content.
    
    Args:
        session (requests.Session): The authenticated session object.
        
    Returns:
        str: HTML content of the page containing the user list.
        None: If the request fails.
    """
    url = "https://www.metamob.fr/utilisateur"
    try:
        response = session.get(url)
    except Exception as e:
        logger.error("Error during GET request to %s: %s", url, e)
        return None

    if response.status_code == 200:
        logger.info("Successfully retrieved the users page.")
        return response.text
    else:
        logger.error("Failed to retrieve the users page: Status code %s\nResponse: %s", response.status_code, response.text)
        return None

def parse_user_names(html_content):
    """
    Parse le contenu HTML de la page des utilisateurs pour en extraire la liste des noms d'utilisateurs.
    
    Args:
        html_content (str): Le contenu HTML de la page des utilisateurs.
    
    Returns:
        list: Une liste des noms d'utilisateurs extraits.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    user_names = []

    # Trouver toutes les balises <div> avec la classe "utilisateur-nom"
    for nom_div in soup.find_all("div", class_="utilisateur-nom"):
        # Extraire le texte en retirant les espaces superflus
        name = nom_div.get_text(strip=True)
        if name:
            user_names.append(name)
    return user_names

def get_metamob_user_list():
    try:
        session = start_session()
        time.sleep(REQUEST_DELAY)  # Respect the minimal delay after the request.
        # Further actions can be performed using the 'session' object.
        users_html = fetch_users_page(session)
        if users_html is None:
            raise Exception("Failed to retrieve data from {}.".format(url))
    except Exception as e:
        logger.error("Failed to start session: %s", e)
    return parse_user_names(users_html)

def get_local_users(file_name=USER_LIST_FILE_NAME):
    if os.path.exists(file_name):
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                current_users = json.load(f)
            # S'assurer que la structure est bien une liste
            if not isinstance(current_users, dict):
                logger.warning("La structure du JSON dans '%s' n'est pas une liste. On la réinitialise.", file_name)
                current_users = {}
        except (json.JSONDecodeError, IOError) as e:
            current_users = {}
    else:
        current_users = {}
    return current_users

def scrap_user_list(output_file=USER_LIST_FILE_NAME):
    new_users = get_metamob_user_list()
    logger.info("%d utilisateurs ont été trouvés sur le site.", len(new_users))
    current_users = {}
    # Vérifier si le fichier existe et essayer de le charger
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                current_users = json.load(f)
            # S'assurer que la structure est bien une liste
            if not isinstance(current_users, dict):
                logger.warning("The content of %s is not a dictionary. Reinitializing.", output_file)
                current_users = {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Error loading file %s: %s", output_file, e)
            current_users = {}
    else:
        logger.info("File %s does not exist; it will be created.", output_file)

    # Ajouter les nouveaux utilisateurs si manquants
    added_users = []
    for user in new_users:
        if user not in current_users:
            current_users[user] = {}
            added_users.append(user)

    # Sauvegarder uniquement si des mises à jour sont effectuées
    if added_users:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(current_users, f, indent=4, ensure_ascii=False)
            logger.info("Added new users: %s", added_users)
        except IOError as e:
            logger.error("Error writing to file %s: %s", output_file, e)
    else:
        logger.info("No new users to add.")

def load_api_key():
    # Load the API key from input.json
    try:
        with open("input.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            api_key = data["apikey"]
            return api_key
    except FileNotFoundError:
        logger.error("The input.json file was not found.")
        return None
    except KeyError:
        logger.error("The key 'apikey' is missing in input.json.")
        return None

def get_monsters_for_user(username, only_archi=True):
    """
    Retrieves the list of monsters for a given user (pseudo) by calling the API.
    
    The API endpoint is: GET https://api.metamob.fr/utilisateurs/(:pseudo)/monstres
    The API key is expected to be in the 'input.json' file under the key "apikey".
    
    Args:
        username (str): The user's pseudo.
        
    Returns:
        dict or list: The JSON decoded response containing the list of monsters, 
                      or None if the request fails.
    """
    api_key = load_api_key()
    if not api_key:
        logger.error("No API key available. Aborting.")
        return

    # Construct the API URL
    url = f"https://api.metamob.fr/utilisateurs/{username}/monstres"
    headers = {"HTTP-X-APIKEY": api_key}

    try:
        response = requests.get(url, headers=headers)
        # Optional: respect a minimal delay between API calls if needed.
        time.sleep(REQUEST_DELAY)
    except Exception as e:
        logger.error("An error occurred during the API call: %s", e)
        return None

    if response.status_code == 200:
        logger.info("Successfully retrieved monsters for user: %s", username)
        try:
            monsters = response.json()
            if only_archi:
                monsters = [m for m in monsters if m["type"] == "archimonstre"]
            return monsters
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON response for user: %s", username)
            return None
    else:
        logger.error("API request failed (Status code: %s). Response: %s",
                     response.status_code, response.text)
        return None

def get_monsters_for_users(user_list, only_archi=True):
    """
    For each user in the given list, retrieves monster data by calling the API,
    aggregates the responses into one big JSON object, and stores it in a file.
    
    Args:
        user_list (list): List of user names (strings) for which to retrieve monsters.
        
    Returns:
        dict: A dictionary where each key is a username and its value is the corresponding monster data.
    """
    aggregated_data = {}

    nb = len(user_list)
    for i, user in enumerate(user_list):
        logger.info("Processing user: %s - %d/%d", user, i+1, nb)
        monster_data = get_monsters_for_user(user, only_archi=only_archi)
        aggregated_data[user] = monster_data
    return aggregated_data

def store_monsters_for_users(aggregated_data, output_file=USER_MONSTERS_FILE):
    # Save the aggregated data to the specified file.
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(aggregated_data, f, indent=4, ensure_ascii=False)
        logger.info("Aggregated monster data stored in %s", output_file)
    except Exception as e:
        logger.error("Error writing aggregated data to file: %s", e)

def update_monsters_for_users(user_list=[], only_archi=True, output_file=USER_MONSTERS_FILE):
    if len(user_list) == 0:
        user_list = get_local_users()
    monsters = get_monsters_for_users(user_list, only_archi=only_archi)
    store_monsters_for_users(monsters, output_file=output_file)

def get_local_user_monsters(file_name=USER_MONSTERS_FILE):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        logging.error("File %s not found.", file_name)
    except json.JSONDecodeError:
        logging.error("Error decoding JSON from file %s.", file_name)

def count_monster_quantities(data, filter_users=[], only_archi=True, proposed=False):
    """
    Reads the JSON file containing aggregated monster data for each user and computes the total quantity 
    for each monster across all users.
    
    If only_archi is True, only monsters with "type" == "archimonstre" are counted.
    If proposed is True, only monsters propsed for trade are counted (and once per player)
    
    Args:
        only_archi (bool): Whether to count only monsters of type "archimonstre". Default is True.
        file_name (str): The name of the JSON file that contains the aggregated monster data.
        
    Returns:
        dict: A dictionary where the keys are monster names and the values are the total quantities.
    """
    counts = {}

    # 'data' is expected to be a dictionary mapping username to a list of monster dictionaries.
    for user, monsters in data.items():
        if len(filter_users) != 0 and user not in filter_users:
            continue
        if not monsters:
            continue
        for monster in monsters:
            # If filtering to only count "archimonstre", skip if the type does not match.
            if only_archi and monster.get("type", "").lower() != "archimonstre":
                continue

            # Get the monster's name and quantity. We assume quantity defaults to 1 if not provided.
            name = monster.get("nom")
            if proposed:
                quantite = int(monster.get("propose"))
            else:
                quantite = int(monster.get("quantite"))
            if name:
                if name not in counts:
                    counts[name] = {}
                counts[name]["cnt"] = counts[name].get("cnt", 0) + quantite
                counts[name]["data"] = monster

    return counts

def plot_monster_histogram(monster_counts):
    """
    Plots a histogram (bar chart) of the number of monsters for each kind,
    ordered from left to right by increasing count.

    Args:
        monster_counts (dict): A dictionary where keys are monster names
                               and values are their total counts.
    """
    # Sort the monster counts by value (lowest to highest)
    sorted_items = sorted(monster_counts.items(), key=lambda item: item[1]["cnt"])

    # Unzip the sorted list of tuples into two tuples: names and counts.
    names, counts = zip(*sorted_items) if sorted_items else ([], [])

    # Create a new figure for the chart.
    plt.figure()
    plt.bar(names, [c["cnt"] for c in counts])
    plt.xlabel("Monster Kind")
    plt.ylabel("Count")
    plt.title("Histogram of Monster Quantities by Kind\n(Ordered from lowest to highest)")

    # Rotate x-axis labels for better readability if needed.
    plt.xticks(rotation=45, ha="right")

    # Adjust layout to ensure all labels are visible.
    plt.tight_layout()

    # Show the plot.
    plt.show()

def print_monster_extremes(monster_counts, n=10, verbose=True):
    """
    Prints the n most rare and n most common monsters based on their total count.
    
    The monster_counts dictionary is structured as follows:
      {
          "monster_name": {"cnt": count, "data": full_json_data},
          ...
      }
    
    Args:
        monster_counts (dict): Dictionary with monster names as keys and a dictionary
                               containing "cnt" and "data" as values.
        n (int): Number of extreme entries (rare and common) to print (default is 10).
    """
    # Sort the items by the count value ("cnt"), in ascending order
    sorted_items = sorted(monster_counts.items(), key=lambda item: item[1]["cnt"])

    # Determine how many items we can display (if there are fewer than n monsters)
    n = min(n, len(sorted_items))

    # The n most rare monsters: the first n items (lowest counts)
    rare_monsters = sorted_items[:n]

    # The n most common monsters: the last n items (highest counts), reversed to show highest first
    common_monsters = sorted_items[-n:][::-1]

    display_monsters = rare_monsters + common_monsters
    max_archi_width = max(len(m[0]) for m in display_monsters)
    max_monstre_width = max(len(m[1]['data']['nom_normal']) for m in display_monsters)+16
    max_zone_width = max(len(m[1]['data']['zone']) for m in display_monsters)
    max_szone_width = max(len(m[1]['data']['souszone']) for m in display_monsters)
    sszone = [m[1]['data']['zone'] + m[1]['data']['souszone'] for m in display_monsters]
    max_szzone_width = max(len(s) for s in sszone) + 3

    # Print results
    print(f"Top {n} Most Rare Monsters:")
    for i, (monster, info) in enumerate(rare_monsters):
        sm = f"(sous-monstre: {info['data']['nom_normal']})"
        szz = f"{info['data']['souszone']} ({info['data']['zone']})"
        if verbose:
            print(f"#{i+1:<2} {monster:<{max_archi_width}}: {info['cnt']:3} {sm:<{max_monstre_width}} - {szz:<{max_szzone_width}} - etape {info['data']['etape']}")
        else:
            print(f"#{i+1:<2} {monster:<{max_archi_width}} - {info['data']['souszone']} ({info['data']['zone']})")

    print(f"\nTop {n} Most Common Monsters:")
    for i, (monster, info) in enumerate(common_monsters):
        sm = f"(sous-monstre: {info['data']['nom_normal']})"
        szz = f"{info['data']['souszone']} ({info['data']['zone']})"
        if verbose:
            print(f"#{i+1:<2} {monster:<{max_archi_width}}: {info['cnt']:3} {sm:<{max_monstre_width}} - {szz:<{max_szzone_width}} - etape {info['data']['etape']}")
        else:
            print(f"#{i+1:<2} {monster:<{max_archi_width}} - {info['data']['souszone']} ({info['data']['zone']})")

def print_user_monster_list_data(player_monster_list, full_user_data):
    def len_list(f):
        l = []
        for p, d in full_user_data.items():
            if p in [p for p, _ in player_monster_list] and f in d:
                l.append(len(d[f]))
        return max(l)

    max_metam_pseudo_width = max(len(p) for p, _ in player_monster_list)
    max_monster_width = max(len(m) for _, m in player_monster_list)
    max_pseudo_width = len_list('pseudo')
    max_link_width = len_list('lien')
    sl = {}
    for p, m in player_monster_list:
        if p in full_user_data and 'pseudo' in full_user_data[p]:
            d = full_user_data[p]
            sl[d['derniere_connexion']] = f"{m:{max_monster_width}} - {d['pseudo']:{max_pseudo_width}} (metamob: {p:{max_metam_pseudo_width}}) - {d['lien']:{max_link_width}} - Last loggin: {d['derniere_connexion']}"
        else:
            sl['2000-10-10 12:12:12'] = f"{m:{max_monster_width}} - metamob: {p} - no data"
    sorted_keys = sorted(sl.keys(), key=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))
    for key in sorted_keys:
        print(f"{sl[key]}")

def find_players_proposing(monster_name, aggregated_data):
    """
    Searches for all players that are proposing (selling/trading) a given monster.
    
    Args:
        monster_name (str): The monster's name to search for.
        aggregated_data (dict): A dictionary mapping username to a list of monster records.
             Each monster record is expected to be a dictionary containing at least:
             - "nom": Name of the monster.
             - "propose": "1" if the player is offering the monster (or 1), "0" otherwise.
    
    Returns:
        list: A list of dictionaries with keys:
              - "username": The username.
              - "monster": The monster record matching the criteria.
    """
    result = []
    for username, monsters in aggregated_data.items():
        for monster in monsters:
            # Compare monster names case-insensitively.
            if monster_name.lower() in monster.get("nom", "").lower() and str(monster.get("propose", "0")) == "1":
                #result.append({"username": username, "monster": monster})
                result.append((username, monster.get("nom", "")))
    return result


def find_players_researching(monster_name, aggregated_data):
    """
    Searches for all players that are researching (looking to acquire) a given monster.
    
    Args:
        monster_name (str): The monster's name to search for.
        aggregated_data (dict): A dictionary mapping username to a list of monster records.
             Each monster record is expected to be a dictionary containing at least:
             - "nom": Name of the monster.
             - "recherche": "1" if the player is looking for the monster (or 1), "0" otherwise.
    
    Returns:
        list: A list of dictionaries with keys:
              - "username": The username.
              - "monster": The monster record matching the criteria.
    """
    result = []
    for username, monsters in aggregated_data.items():
        for monster in monsters:
            #print(monster["nom"], monster_name, monster["recherche"])
            if monster_name.lower() in monster.get("nom", "").lower() and str(monster.get("recherche", "0")) == "1":
                #result.append({"username": username, "monster": monster})
                result.append((username, monster.get("nom", "")))
    return result

def compare_monster_files(old_data, new_data, proposed=True):
    """
    Compare two versions of a monsters JSON file (each as a dictionary) and
    compute the differences for each player.

    - If proposed is True, the function compares the set of monsters _proposed_ for trade.
      For each player, we consider a given monster as “proposed” if at least one record has 
      "propose" == "1". (The "quantite" field is ignored in this mode.)
    - If proposed is False, the function compares the total quantities (summed using "quantite")
      with a default of 0 when not found.
    - If a player's data is None or missing, that player is considered as absent from that dataset.
    - The function prints output only for players that show differences. Also, if a player
      appears in new_data but was missing (or had no data) in old_data, a special notice is shown.
    
    Args:
        old_data (dict): Dictionary representing the old monsters JSON file.
        new_data (dict): Dictionary representing the new monsters JSON file.
        proposed (bool): If True, compare only the _proposed_ status;
                         if False, compare total quantities.
    """

    def group_monsters(monster_list, use_proposed):
        """
        Group a list of monster records by their name.

        - When use_proposed is True: for each monster, return 1 if at least one record's "propose" is "1",
          or 0 otherwise.
        - When use_proposed is False: sum the integer value of "quantite" for each monster (defaulting to 0 if absent).
        """
        if not monster_list:
            return {}
        grouped = {}
        if use_proposed:
            for m in monster_list:
                name = m.get("nom")
                if not name:
                    continue
                # Set presence to 1 if any record shows proposed == "1"
                flag = 1 if str(m.get("propose", "0")) == "1" else 0
                if name not in grouped:
                    grouped[name] = flag
                else:
                    # Once proposed, always mark as 1.
                    if grouped[name] == 0 and flag == 1:
                        grouped[name] = 1
            return grouped
        else:
            for m in monster_list:
                name = m.get("nom")
                if not name:
                    continue
                try:
                    qty = int(m.get("quantite", 0))
                except (ValueError, TypeError):
                    qty = 0
                grouped[name] = grouped.get(name, 0) + qty
            return grouped

    # Process each player in new_data.
    for player, new_monsters in new_data.items():
        # If new data for a player is None or empty, consider that player's data as missing.
        if not new_monsters:
            continue

        # Get the old monsters list (if None or missing, treat as empty list).
        old_monsters = old_data.get(player) if old_data.get(player) is not None else []

        new_group = group_monsters(new_monsters, proposed)
        old_group = group_monsters(old_monsters, proposed)

        # Union of all monster names for this player.
        monster_names = set(new_group.keys()) | set(old_group.keys())
        messages = []
        for mon in sorted(monster_names):
            old_value = old_group.get(mon, 0)
            new_value = new_group.get(mon, 0)
            if new_value != old_value:
                if proposed:
                    # In proposed mode, new_value and old_value are either 0 or 1.
                    if new_value == 1 and old_value == 0:
                        messages.append(f"  Added monster '{mon}' to the market")
                    elif new_value == 0 and old_value == 1:
                        messages.append(f"  Removed monster '{mon}' from the market")
                else:
                    diff = new_value - old_value
                    if diff > 0:
                        messages.append(f"  Added {diff} of monster '{mon}' (old: {old_value}, new: {new_value})")
                    else:
                        messages.append(f"  Removed {-diff} of monster '{mon}' (old: {old_value}, new: {new_value})")
        # Only display output for this player if there are differences.
        if messages:
            # If the player is new or has no old data, print a special message.
            if player not in old_data or not old_monsters:
                print(f"Player '{player}' [NEW PLAYER]:")
            else:
                print(f"Player '{player}':")
            for msg in messages:
                print(msg)
            print()  # Blank line for separation.

    # Optionally, report players present in old_data but missing in new_data.
    for player in old_data:
        if player not in new_data or not new_data.get(player):
            print(f"Player '{player}' is missing in the new data (possibly removed from the system).")

def detect_unbalanced_players(data, factor=3):
    """
    Given a dictionary mapping player names to lists of monster records, detect players 
    that have an unbalanced pool of monsters.
    
    A player is considered unbalanced if:
      - They have at least one monster with a count higher than (factor * average) where average is
        computed only over monsters with a nonzero count.
      - They are missing one or more monsters (i.e. count == 0).
      
    Notes:
      - Only records with an "etape" value different from "14" are considered.
      - When a monster is not present in a player's list, its quantity defaults to 0.
      - The output is a list of messages reporting the unbalanced players.
      - In the report, after each monster name the corresponding quantity is shown in parentheses.
      
    Args:
        data (dict): A dictionary mapping player names to lists of monster records.
        factor (int or float): The multiplier above the average that qualifies a monster as "high".
    
    Returns:
        list: A list of strings. Each string reports a player deemed unbalanced and explains why.
    """
    # Build the full set of monster names across the dataset (ignoring records with "etape" == "14")
    full_monster_set = set()
    for player, monsters in data.items():
        if not monsters:
            continue  # Skip players with missing data.
        for m in monsters:
            if m.get("etape") == "14":
                continue
            name = m.get("nom")
            if name:
                full_monster_set.add(name)

    results = []
    # For each player, build a complete count per monster (default 0 if not present)
    for player, monsters in data.items():
        if not monsters:
            # Skip players with missing or None data.
            continue

        # Initialize counts for every monster in the full set to 0.
        player_counts = {mon: 0 for mon in full_monster_set}
        for m in monsters:
            if m.get("etape") == "34":
                continue
            mon_name = m.get("nom")
            if not mon_name:
                continue
            try:
                qty = int(m.get("quantite", 0))
            except (ValueError, TypeError):
                qty = 0
            player_counts[mon_name] = player_counts.get(mon_name, 0) + qty

        # Compute the average only over monsters with count > 0.
        non_zero_counts = [count for count in player_counts.values() if count > 0]
        avg = (sum(non_zero_counts) / len(non_zero_counts)) if non_zero_counts else 0

        # Define "high" as any monster count greater than factor * avg.
        high_monsters = [f"{mon} ({player_counts[mon]})"
                         for mon, count in player_counts.items() if count > factor * avg]
        # Missing monsters are those with a count of 0.
        missing_monsters = [f"{mon} (0)" for mon, count in player_counts.items() if count == 0]

        # Report the player if they have at least one high monster and at least one missing monster.
        if high_monsters and missing_monsters:
            msg = (f"Player '{player}' is unbalanced: high count for {', '.join(high_monsters)} "
                   f"(average over owned monsters: {avg:.2f}, threshold: {factor}×average).")
            results.append(msg)
    return results

def update_user_data_from_api(users, output_file=USER_LIST_FILE_NAME):
    """
    For each user in the provided dictionary, perform an API GET request to retrieve
    their data and update the dictionary accordingly. Finally, write the updated dictionary
    to the output file.
    
    The API endpoint used is: GET /utilisateurs/(:pseudo)
    (e.g., "https://api.metamob.fr/utilisateurs/{username}")
    
    Args:
        users (dict): A dictionary where each key is a username and its value is a dictionary
                      (initially empty) for storing user data.
        output_file (str): The filename where the updated users data will be saved.
                           Default value is set to USER_LIST_FILE_NAME.
    """
    api_key = load_api_key()
    if not api_key:
        logger.error("No API key available. Aborting.")
        return

    base_url = "https://api.metamob.fr/utilisateurs"  # Adjust base URL if needed.
    headers = {"HTTP-X-APIKEY": api_key}

    if isinstance(users, dict):
        users_data = users
    else:
        users_data = {}

    # Iterate over each user in the provided dictionary.
    nb_users = len(users)
    for i, username in enumerate(users):
        url = f"{base_url}/{username}"
        try:
            response = requests.get(url, headers=headers)
            time.sleep(REQUEST_DELAY)  # Respect the delay between API calls.
        except Exception as e:
            logger.error("Error retrieving data for user '%s': %s", username, e)
            continue

        if response.status_code == 200:
            try:
                user_data = response.json()
                users_data[username] = user_data
                logger.info("Updated data for user '%s' - %d/%d", username, i+1, nb_users)
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON for user '%s'.", username)
        else:
            logger.error("API request failed for user '%s' (Status: %s). Response: %s",
                         username, response.status_code, response.text)

    # Write the updated users dictionary to the output file.
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
        logger.info("Updated user data written to '%s'.", output_file)
    except Exception as e:
        logger.error("Error writing updated user data to file '%s': %s", output_file, e)


def main():
    # Create the top-level parser.
    parser = argparse.ArgumentParser(
        description="Script to manage monster trading functionalities."
    )

    # Add subparsers for each command.
    subparsers = parser.add_subparsers(dest="command", help="Command to execute", required=True)

    # Subparser for "find_proposing".
    parser_find_prop = subparsers.add_parser(
        "find_proposing",
        help="Find players proposing the specified monster."
    )
    parser_find_prop.add_argument(
        "monster",
        type=str,
        help="Name of the monster to search for."
    )
    parser_find_res = subparsers.add_parser(
        "find_researching",
        help="Find players researching the specified monster."
    )
    parser_find_res.add_argument(
        "monster",
        type=str,
        help="Name of the monster to search for."
    )
    parser_scrap_users = subparsers.add_parser(
        "scrap_users",
        help="Scrap the user list from the website (without the api). The user list will be updated with those. Typically this will get the 200 most recent logged-in users."
    )
    parser_scrap_users.add_argument(
        "--filename", "-f",
        type=str,
        default=USER_LIST_FILE_NAME,
        help="Filename where to store the data"
    )
    parser_refresh_users = subparsers.add_parser(
        "refresh_users",
        help="Refresh user data of each cached users from the website."
    )
    parser_refresh_users.add_argument(
        "--filename", "-f",
        type=str,
        default=USER_LIST_FILE_NAME,
        help="Filename to update"
    )
    parser_refresh_monsters = subparsers.add_parser(
        "refresh_monsters",
        help="Refresh the monsters of each cached users from the website."
    )
    parser_refresh_monsters.add_argument(
        "--filename", "-f",
        type=str,
        default=USER_MONSTERS_FILE,
        help="Filename where to store the data"
    )
    parser_hist = subparsers.add_parser(
        "hist",
        help="Plot a histogram with the frequency of the monsters."
    )
    parser_hist.add_argument(
        "--only-proposed", "-p",
        action="store_true",
        help="Only use data of the monster proposed for trading"
    )
    parser_stats = subparsers.add_parser(
        "stats",
        help="Display monsters stats."
    )
    parser_stats.add_argument(
        "--only-proposed", "-p",
        action="store_true",
        help="Only use data of the monster proposed for trading"
    )
    parser_stats.add_argument(
        "-n",
        type=int,
        default=10,
        help="Number of monsters to display for top n"
    )
    parser_stats.add_argument(
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser_cmp = subparsers.add_parser(
        "compare",
        help="Compare 2 versions of the monsters json file."
    )
    parser_cmp.add_argument(
        "--only-proposed", "-p",
        action="store_true",
        help="Only use data of the monster proposed for trading"
    )
    subparsers.add_parser(
        "test",
        help="test command"
    )

    # Parse the arguments.
    args = parser.parse_args()

    # Dispatch to the appropriate function based on the subcommand.
    if args.command == "find_proposing":
        monsters = get_local_user_monsters()
        playerslist = find_players_proposing(args.monster, monsters)
        users = get_local_users()
        logger.info("Players proposing {}:".format(args.monster))
        print_user_monster_list_data(playerslist, users)
        #print(find_players_proposing("Tronquette la Réduite", monsters))
    elif args.command == "find_researching":
        monsters = get_local_user_monsters()
        #print(monsters)
        playerslist = find_players_researching(args.monster, monsters)
        users = get_local_users()
        logger.info("Players searching {}:".format(args.monster))
        print_user_monster_list_data(playerslist, users)
        #print(find_players_researching("Tronquette la Réduite", monsters))
    elif args.command == "scrap_users":
        scrap_user_list(output_file=args.filename)
    elif args.command == "refresh_users":
        users = get_local_users(file_name=args.filename)
        update_user_data_from_api(users, output_file=args.filename)
    elif args.command == "refresh_monsters":
        update_monsters_for_users(output_file=args.filename)
        #update_monsters_for_users(user_list=["Kerman"])
    elif args.command == "hist":
        monsters = get_local_user_monsters()
        all_counts = count_monster_quantities(monsters, proposed=args.only_proposed)
        plot_monster_histogram(all_counts)
    elif args.command == "stats":
        monsters = get_local_user_monsters()
        all_counts = count_monster_quantities(monsters, proposed=args.only_proposed)
        print_monster_extremes(all_counts, n=args.n, verbose=args.v)
    elif args.command == "compare":
        monsters = get_local_user_monsters()
        newmonsters = get_local_user_monsters("test.json")
        compare_monster_files(monsters, newmonsters, proposed=args.only_proposed)
    elif args.command == "test":
        monsters = get_local_user_monsters()
        res = detect_unbalanced_players(monsters, factor=3)
        for r in res:
            print(r)
    else:
        # This should never happen because 'required=True' forces a subcommand.
        parser.print_help()

# Example usage:
if __name__ == "__main__":
    main()

# ignore player with full sets
# printing of a user: portfolio of monster, maybe sorted from most to least, ignoring the 0
# find when rare monster are put on the market
# ignore player connected to long ago / user scrapping
