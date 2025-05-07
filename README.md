# Principe general

Le but de ce script est d'utiliser l'API metamob pour recuperer les infos du site, les stocker en local et les analyser.

# Mise en place

## Creer un fichier credentials

Creer un fichier input.json comme suit a la racine du projet :
```
{
    "login": "<Votre login metamob (email)>",
    "password": "<Votre mot de passe metamob>",
    "apikey": "<Votre clef d'API metamob>"
}
```

## Extraire les 1eres donnees

Dans un 1er temps il faut extraire les donnees du site. Elles sont ensuite analysees localement.
Cette etape prend un peu de temps car il faut faire une requete pour chaque utilisateur pour recuperer ses monstres.
```
python metamob.py scrap_users # recupere les 200 derniers utilisateurs connectes sur votre serveur (cree le fichier users.json)
python metamob.py refresh_monster # recupere la liste des monstres pour chaque utilisateurs dans le fichier users.json (cree monsters.json)
```
Par defaut le script ne traite que les archimonstres mais un option permet de gerer tout le reste, l'option `-h` est votre meilleure amie.

# Analyse

Top des monstres possedes/sur le marche (voir options avec `-h`).
```
python metamob.py stats    # Donne le top 10 des monstres les plus/moins poseedes par les joueurs
python metamob.py stats -p # Donne le top 10 des monstres les plus/moins proposes a l'echange par les joueurs
```

D'autres commandes sont dispo (histogramme des quantites de monstres, trouver un joueur proposant d'echanger un monstre specifique, ect... -> Option `-h`.

# Bonus

* Doc de l'API metamob https://www.metamob.fr/aide/api
* Creer une clef pour l'API: https://www.metamob.fr/utilisateur/mon_profil -> API

# FAQ

## Pourquoi faut-il le login/mot de passe en plus de la clef API ?

L'endpoint API pour recuperer la liste des utilisateurs n'est pas encore disponibles (https://www.metamob.fr/aide/api#utilisateurs). Pour contourner ce probleme, le script se connecte par la voie habituelle a metamob et scrap la page utilisateur.

## Est-ce que je risque de DDOS metamob ?

L'API est limitee a 60 appels/minute. De base le script est configure pour ne pas exceder cette limite et vous etes tranquille.
