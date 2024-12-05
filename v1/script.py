➜  dossierAdeployer cat script.py                                                                 
import socket
import json
import struct
import os
from collections import defaultdict
import time

# Ports pour chaque phase
PORT1 = 3466
PORT2 = 3467
PORT3 = 3468
PORT4 = 3469

# Chemin vers les fichiers sur les machines
FICHIERS_DIR = "/home/users/yjuarez-24"

# Obtenir le nom de la machine
nom_machine = socket.gethostname()

# Fonction pour recevoir un nombre exact d'octets
def recevoir_exactement(socket_client, n):
    data = b''
    while len(data) < n:
        packet = socket_client.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

# Fonction pour recevoir un message complet
def recevoir_message(socket_client):
    try:
        taille_message_bytes = recevoir_exactement(socket_client, 4)
        if not taille_message_bytes:
            return None
        taille_message = struct.unpack('!I', taille_message_bytes)[0]
        donnees = recevoir_exactement(socket_client, taille_message)
        return donnees.decode('utf-8') if donnees else None
    except Exception as e:
        print(f"{nom_machine} : Erreur lors de la réception du message : {e}")
        return None

# Fonction pour envoyer un message
def envoyer_message(socket_client, message):
    try:
        message_bytes = message.encode('utf-8')
        taille_message = struct.pack('!I', len(message_bytes))
        socket_client.sendall(taille_message + message_bytes)
    except Exception as e:
        print(f"{nom_machine} : Erreur lors de l'envoi du message : {e}")

# Phase 1 : Mappage
def phase_1():
    print(f"PHASE 1 : Bonjour, je suis la machine '{nom_machine}', en attente de connexion sur le port {PORT1}")
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind(('0.0.0.0', PORT1))
    serveur_socket.listen(1)
    print(f"PHASE 1 : Le serveur écoute sur le port {PORT1}...")

    socket_client, adresse = serveur_socket.accept()
    print(f"PHASE 1 : Connexion acceptée de {adresse}")

    # Recevoir les données initiales (fichiers assignés et liste des machines)
    message = recevoir_message(socket_client)
    if not message:
        print(f"{nom_machine} : Aucune donnée reçue en PHASE 1.")
        return False

    donnees = json.loads(message)
    liste_machines = donnees["machines"]
    fichiers_assignes = donnees["files"]

    print(f"{nom_machine} : Liste des machines reçue : {liste_machines}")
    print(f"{nom_machine} : Fichiers assignés : {fichiers_assignes}")

    # Traiter les fichiers (Map)
    resultats = defaultdict(int)
    for fichier in fichiers_assignes:
        chemin_fichier = os.path.join(FICHIERS_DIR, fichier)
        if not os.path.exists(chemin_fichier):
            print(f"{nom_machine} : Le fichier {chemin_fichier} n'existe pas.")
            continue

        with open(chemin_fichier, 'r', encoding='utf-8') as f:
            for ligne in f:
                for mot in ligne.strip().split():
                    resultats[mot] += 1

    # Sauvegarder les résultats locaux
    fichier_sortie_map = f"map_{nom_machine}.json"
    with open(fichier_sortie_map, 'w', encoding='utf-8') as f:
        json.dump(resultats, f, ensure_ascii=False, indent=4)

    print(f"{nom_machine} : Mappage terminé. Résultats sauvegardés dans {fichier_sortie_map}")    

    # Confirmer la fin au coordinateur
    envoyer_message(socket_client, "OK FIN PHASE 1")
    print(f"{nom_machine} : Envoyé 'OK FIN PHASE 1' au coordinateur.")

    socket_client.close()
    serveur_socket.close()
    return True

# Phase 2 : Shuffle
def phase_2():
    print(f"PHASE 2 : Bonjour, je suis la machine '{nom_machine}', en attente de connexion sur le port {PORT2}")
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind(('0.0.0.0', PORT2))
    serveur_socket.listen(1)
    print(f"PHASE 2 : Le serveur écoute sur le port {PORT2}...")

    socket_client, adresse = serveur_socket.accept()
    print(f"PHASE 2 : Connexion acceptée de {adresse}")

    # Pause de 3 secondes avant de recevoir
    time.sleep(3)

    # Recevoir 'GO PHASE 2'
    message = recevoir_message(socket_client)
    if message != "GO PHASE 2":
        print(f"{nom_machine} : Message inattendu en PHASE 2 : {message}")
        return False

    print(f"{nom_machine} : Reçu 'GO PHASE 2'. Réalisation du shuffle.")

    # Réaliser le shuffle
    shuffle_data = defaultdict(int)
    fichier_sortie_map = f"map_{nom_machine}.json"
    if not os.path.exists(fichier_sortie_map):
        print(f"{nom_machine} : Fichier {fichier_sortie_map} introuvable pour le shuffle.")       
        envoyer_message(socket_client, "ERROR PHASE 2")
        return False

    # Charger les données locales
    with open(fichier_sortie_map, 'r', encoding='utf-8') as f:
        local_map = json.load(f)

    # Ajouter les données locales au shuffle
    for mot, compteur in local_map.items():
        shuffle_data[mot] += compteur

    # Sauvegarder les données de shuffle
    fichier_sortie_shuffle = f"shuffle_{nom_machine}.json"
    with open(fichier_sortie_shuffle, 'w', encoding='utf-8') as f:
        json.dump(shuffle_data, f, ensure_ascii=False, indent=4)

    print(f"{nom_machine} : Shuffle terminé. Données sauvegardées dans {fichier_sortie_shuffle}") 

    # Confirmer la fin de la phase 2 au coordinateur
    envoyer_message(socket_client, "FIN PHASE 2")
    print(f"{nom_machine} : Envoyé 'FIN PHASE 2' au coordinateur.")

    socket_client.close()
    serveur_socket.close()
    return True

# Phase 3 : Réduction
def phase_3():
    print(f"PHASE 3 : Bonjour, je suis la machine '{nom_machine}', en attente de connexion sur le port {PORT3}")
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind(('0.0.0.0', PORT3))
    serveur_socket.listen(1)
    print(f"PHASE 3 : Le serveur écoute sur le port {PORT3}...")

    socket_client, adresse = serveur_socket.accept()
    print(f"PHASE 3 : Connexion acceptée de {adresse}")

    # Pause de 3 secondes avant de recevoir
    time.sleep(3)

    # Recevoir 'GO PHASE 3'
    message = recevoir_message(socket_client)
    if message != "GO PHASE 3":
        print(f"{nom_machine} : Message inattendu en PHASE 3 : {message}")
        return False

    print(f"{nom_machine} : Reçu 'GO PHASE 3'. Réalisation de la réduction.")

    # Réaliser la réduction
    fichier_sortie_shuffle = f"shuffle_{nom_machine}.json"
    if not os.path.exists(fichier_sortie_shuffle):
        print(f"{nom_machine} : Fichier {fichier_sortie_shuffle} introuvable pour réduction.")    
        envoyer_message(socket_client, "ERROR PHASE 3")
        return False

    with open(fichier_sortie_shuffle, 'r', encoding='utf-8') as f:
        donnees_shuffle = json.load(f)

    # Modification pour inclure toutes les données
    resultats_reduction = sorted(donnees_shuffle.items(), key=lambda x: x[1], reverse=True)       
    fichier_sortie_reduction = f"reduction_{nom_machine}.json"

    with open(fichier_sortie_reduction, 'w', encoding='utf-8') as f:
        json.dump(dict(resultats_reduction), f, ensure_ascii=False, indent=4)

    print(f"{nom_machine} : Réduction terminée. Résultats sauvegardés dans {fichier_sortie_reduction}")

    envoyer_message(socket_client, json.dumps(dict(resultats_reduction), ensure_ascii=False))     
    print(f"{nom_machine} : Résultats de réduction envoyés au coordinateur.")

    socket_client.close()
    serveur_socket.close()
    return True

# Phase 4 : Finalisation
def phase_4():
    print(f"PHASE 4 : Bonjour, je suis la machine '{nom_machine}', en attente de connexion sur le port {PORT4}")
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serveur_socket.bind(('0.0.0.0', PORT4))
    serveur_socket.listen(1)
    print(f"PHASE 4 : Le serveur écoute sur le port {PORT4}...")

    socket_client, adresse = serveur_socket.accept()
    print(f"PHASE 4 : Connexion acceptée de {adresse}")

    # Pause de 3 secondes avant de recevoir
    time.sleep(3)

    # Recevoir 'GO PHASE 4'
    message = recevoir_message(socket_client)
    if message != "GO PHASE 4":
        print(f"{nom_machine} : Message inattendu en PHASE 4 : {message}")
        return False

    print(f"{nom_machine} : Reçu 'GO PHASE 4'. Nettoyage des fichiers temporaires.")

    # Nettoyage des fichiers temporaires
    fichiers_temp = [
        f"map_{nom_machine}.json",
        f"shuffle_{nom_machine}.json",
        f"reduction_{nom_machine}.json"
    ]
    for fichier in fichiers_temp:
        if os.path.exists(fichier):
            os.remove(fichier)
            print(f"{nom_machine} : Fichier temporaire {fichier} supprimé.")

    # Confirmer la fin de la phase 4 au coordinateur
    envoyer_message(socket_client, "FIN PHASE 4")
    print(f"{nom_machine} : Envoyé 'FIN PHASE 4' au coordinateur.")

    socket_client.close()
    serveur_socket.close()
    return True

# Fonction principale
def main():
    if not phase_1():
        return
    if not phase_2():
        return
    if not phase_3():
        return
    if not phase_4():
        return
    print(f"{nom_machine} : Toutes les phases terminées avec succès.")

if __name__ == "__main__":
    main()
