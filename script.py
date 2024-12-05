import signal
import sys
import socket
import json
import struct
import threading
import os
import time
from collections import defaultdict

# Définir les ports pour chaque phase
PORT1 = 3466  # Phase 1
PORT2 = 3467  # Phase 2
PORT3 = 3468  # Phase 3

# Variables globales
nom_machine = socket.gethostname()
mots = []
mots_recus = defaultdict(int)
machines_recues = []
reduction_terminee = False  # Variable pour contrôler la phase 3

# Dictionnaires pour stocker les connexions par phase (si nécessaire)
conn_phase1 = {}
conn_phase2 = {}
conn_phase3 = {}

# Liste pour maintenir des références aux threads de réception
threads_reception = []

# Événements pour synchroniser les phases
phase_4_terminee = threading.Event()

# Fonction pour gérer les signaux de terminaison
def gestion_signal(sig, frame):
    liberer_ports()
    sys.exit(0)

# Enregistrer le gestionnaire de signaux
signal.signal(signal.SIGINT, gestion_signal)
signal.signal(signal.SIGTERM, gestion_signal)

print(f"Bonjour, je suis la machine '{nom_machine}', utilisant le port {PORT1} pour la PHASE 1, {PORT2} pour la PHASE 2 et {PORT3} pour la PHASE 3")

# Fonction pour recevoir un nombre exact d'octets
def recevoir_exact(socket_client, n):
    donnees = b''
    while len(donnees) < n:
        paquet = socket_client.recv(n - len(donnees))
        if not paquet:
            return None
        donnees += paquet
    return donnees

# Fonction pour recevoir un message
def recevoir_message(socket_client):
    try:
        taille_message_bytes = recevoir_exact(socket_client, 4)
        if not taille_message_bytes:
            return None
        taille_message = struct.unpack('!I', taille_message_bytes)[0]
        donnees = recevoir_exact(socket_client, taille_message)
        return donnees.decode('utf-8') if donnees else None
    except Exception as e:
        print(f"{nom_machine} : Erreur lors de la réception du message : {e}")
        return None

# Fonction pour envoyer un message à un socket
def envoyer_message(socket_client, message):
    try:
        message_bytes = message.encode('utf-8')
        socket_client.sendall(struct.pack('!I', len(message_bytes)))
        socket_client.sendall(message_bytes)
    except Exception as e:
        print(f"{nom_machine} : Erreur lors de l'envoi du message : {e}")

# Fonction pour gérer la connexion pour la phase 1
def gerer_connexion_phase1(socket_client, adresse_client):
    try:
        # Recevoir la liste des machines
        liste_machines = recevoir_message(socket_client)
        if liste_machines:
            machines_recues.extend(json.loads(liste_machines))
            print(f"{nom_machine} : Liste des machines reçue : {machines_recues}")

        # Recevoir des messages spécifiques
        while True:
            message = recevoir_message(socket_client)
            if not message:
                break

            if message == "FIN PHASE 1":
                envoyer_message(socket_client, "OK FIN PHASE 1")
                print(f"{nom_machine} : Envoyé 'OK FIN PHASE 1' au coordinateur")
                break
            else:
                mots.append(message)
                print(f"{nom_machine} : Mot reçu : {message}")

    except Exception as e:
        print(f"{nom_machine} : Erreur dans la PHASE 1 : {e}")

# Fonction pour gérer la connexion pour la phase 2
def gerer_connexion_phase2(socket_client, adresse_client):
    try:
        # Recevoir 'GO PHASE 2'
        message = recevoir_message(socket_client)
        if message == "GO PHASE 2":
            print(f"{nom_machine} : Reçu 'GO PHASE 2' du coordinateur")
            demarrer_phase2(socket_client)
    except Exception as e:
        print(f"{nom_machine} : Erreur dans la PHASE 2 : {e}")

# Fonction pour gérer la connexion pour la phase 3
def gerer_connexion_phase3(socket_client, adresse_client):
    try:
        # Recevoir 'GO PHASE 3'
        message = recevoir_message(socket_client)
        if message == "GO PHASE 3":
            print(f"{nom_machine} : Reçu 'GO PHASE 3' du coordinateur")
            demarrer_phase3(socket_client)
    except Exception as e:
        print(f"{nom_machine} : Erreur dans la PHASE 3 : {e}")

# Fonction pour gérer la connexion pour la phase 4
def gerer_connexion_phase4(socket_client, adresse_client):
    try:
        # Recevoir 'GO PHASE 4'
        message = recevoir_message(socket_client)
        if message == "GO PHASE 4":
            print(f"{nom_machine} : Reçu 'GO PHASE 4' du coordinateur")
            envoyer_message(socket_client, "FIN PHASE 4")
            print(f"{nom_machine} : Envoyé 'FIN PHASE 4' au coordinateur")
            phase_4_terminee.set()
    except Exception as e:
        print(f"{nom_machine} : Erreur dans la PHASE 4 : {e}")

# Fonction pour démarrer la phase 2 (Shuffle)
def demarrer_phase2(socket_client_coordinateur):
    connexions_phase2 = {}
    try:
        # Connecter aux autres machines pour la PHASE 2
        for machine in machines_recues:
            if machine != nom_machine:
                socket_client = essayer_connexion(machine, PORT2)
                if socket_client:
                    connexions_phase2[machine] = socket_client
                    thread = threading.Thread(target=gerer_reception_phase2, args=(machine, socket_client))
                    thread.start()
                    threads_reception.append(thread)

        # Envoyer les mots aux autres machines
        for mot in mots:
            for machine_dest, sock in connexions_phase2.items():
                envoyer_message(sock, mot)
                print(f"{nom_machine} : Mot '{mot}' envoyé à {machine_dest}")
            # Traitement local
            mots_recus[mot] += 1
            print(f"{nom_machine} : Mot '{mot}' traité localement")

        # Envoyer 'FIN PHASE 2' à toutes les machines
        for machine, sock in connexions_phase2.items():
            envoyer_message(sock, "FIN PHASE 2")
            print(f"{nom_machine} : Envoyé 'FIN PHASE 2' à {machine}")

        # Envoyer 'FIN PHASE 2' au coordinateur
        envoyer_message(socket_client_coordinateur, "FIN PHASE 2")
        print(f"{nom_machine} : Envoyé 'FIN PHASE 2' au coordinateur")

    except Exception as e:
        print(f"{nom_machine} : Erreur lors du démarrage de la PHASE 2 : {e}")

# Fonction pour gérer la réception des mots dans la phase 2
def gerer_reception_phase2(machine, socket_client):
    try:
        while True:
            message = recevoir_message(socket_client)
            if message == "FIN PHASE 2":
                break
            elif message:
                mots_recus[message] += 1
                print(f"{nom_machine} : Mot '{message}' reçu pendant la PHASE 2")
    except Exception as e:
        print(f"{nom_machine} : Erreur lors de la réception dans la PHASE 2 de {machine} : {e}")  
    finally:
        socket_client.close()

# Fonction pour démarrer la phase 3 (Réduction)
def demarrer_phase3(socket_client_coordinateur):
    try:
        # Effectuer la réduction locale
        resultat_reduction = dict(mots_recus)
        envoyer_message(socket_client_coordinateur, json.dumps(resultat_reduction))
        print(f"{nom_machine} : Résultat de réduction envoyé au coordinateur.")

        # Envoyer 'FIN PHASE 3' au coordinateur
        envoyer_message(socket_client_coordinateur, "FIN PHASE 3")
        print(f"{nom_machine} : Envoyé 'FIN PHASE 3' au coordinateur")
    except Exception as e:
        print(f"{nom_machine} : Erreur dans la PHASE 3 : {e}")

# Fonction pour essayer de se connecter à une machine dans une phase spécifique
def essayer_connexion(machine, port, retries=5, temps_attente=3):
    socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for i in range(retries):
        try:
            socket_client.connect((machine, port))
            print(f"Connexion établie avec {machine} sur le port {port} après {i+1} essai(s).")   
            return socket_client
        except Exception as e:
            print(f"Erreur lors de la connexion avec {machine} sur le port {port} : {e}. Nouvel essai ({i+1}/{retries})...")
            time.sleep(temps_attente)
    print(f"Impossible de se connecter avec {machine} sur le port {port} après {retries} essais.")
    return None

# Fonction pour libérer les ports et fermer les connexions
def liberer_ports():
    print("Fermeture des ports et fin des connexions...")
    # Fermer toutes les connexions
    for dict_conn in [conn_phase1, conn_phase2, conn_phase3]:
        for machine, socket_client in dict_conn.items():
            try:
                socket_client.close()
                print(f"Connexion à {machine} fermée.")
            except Exception as e:
                print(f"Erreur lors de la fermeture de la connexion avec {machine} : {e}")        
    # Libérer les ports
    os.system(f"fuser -k {PORT1}/tcp || true")
    os.system(f"fuser -k {PORT2}/tcp || true")
    os.system(f"fuser -k {PORT3}/tcp || true")
    print(f"Ports {PORT1}, {PORT2} et {PORT3} libérés correctement.")

# Fonction pour gérer les connexions entrantes dans une phase spécifique
def gerer_serveur_phase(port, fonction_handler, phase):
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.bind(('0.0.0.0', port))
    serveur_socket.listen(len(machines_recues) if machines_recues else 1)
    phase_num = port - 3465
    print(f"PHASE {phase_num} : Le serveur écoute sur le port {port}...")
    while True:
        socket_client, adresse_client = serveur_socket.accept()
        thread = threading.Thread(target=fonction_handler, args=(socket_client, adresse_client))  
        thread.start()
        threads_reception.append(thread)

# Fonction pour générer un fichier unique des résultats
def generer_fichier_unique():
    print("Génération du fichier unique des résultats...")
    pass

# Fonction principale
def main():
    # Démarrer les threads pour gérer les connexions entrantes dans chaque phase
    thread_serveur_phase1 = threading.Thread(target=gerer_serveur_phase, args=(PORT1, gerer_connexion_phase1, 1))
    thread_serveur_phase1.start()
    threads_reception.append(thread_serveur_phase1)

    thread_serveur_phase2 = threading.Thread(target=gerer_serveur_phase, args=(PORT2, gerer_connexion_phase2, 2))
    thread_serveur_phase2.start()
    threads_reception.append(thread_serveur_phase2)

    thread_serveur_phase3 = threading.Thread(target=gerer_serveur_phase, args=(PORT3, gerer_connexion_phase3, 3))
    thread_serveur_phase3.start()
    threads_reception.append(thread_serveur_phase3)

    # Attendre un court instant pour s'assurer que les serveurs sont prêts
    time.sleep(2)

    # Le worker n'agit pas comme coordinateur, il n'a donc pas besoin de se connecter aux machines
    # Toutes les connexions sont initiées par le coordinateur

    # Attendre que la PHASE 4 soit terminée
    phase_4_terminee.wait()

    # Libérer les ports et fermer les connexions
    liberer_ports()

    print("Communication terminée.")

if __name__ == "__main__":
    main()
