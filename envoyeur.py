import socket
import json
import struct
import threading
import time
import os
from collections import defaultdict

# Définir les ports pour chaque phase
PORT1 = 3466  # Phase 1
PORT2 = 3467  # Phase 2
PORT3 = 3468  # Phase 3
PORT4 = 3469  # Phase 4 (Nouveau port pour la Phase 4)

# Lire les adresses des machines depuis le fichier machines.txt
with open('machines.txt', 'r') as file:
    machines = [line.strip() for line in file.readlines() if line.strip()]

# Dictionnaires pour stocker les connexions par phase
conn_phase1 = {}
conn_phase2 = {}
conn_phase3 = {}
conn_phase4 = {}  # Connexions pour la Phase 4

# Listes pour contrôler les phases
tab_fin_phase_1 = []
tab_fin_phase_2 = []
tab_fin_phase_3 = []
tab_fin_phase_4 = []

# Dictionnaire pour stocker les résultats de réduction
resultats_reduction = {}

# Mutex pour synchroniser l'accès aux listes et dictionnaires
lock = threading.Lock()

# Sémaphores pour synchroniser les phases
semaphore_phase_1 = threading.Semaphore(0)
semaphore_phase_2 = threading.Semaphore(0)
semaphore_phase_3 = threading.Semaphore(0)
semaphore_phase_4 = threading.Semaphore(0)

# Liste pour maintenir des références aux threads de réception
threads_reception = []

# Fonction pour recevoir un nombre exact d'octets
def recevoir_exactement(socket_client, n):
    data = b''
    while len(data) < n:
        packet = socket_client.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

# Fonction pour recevoir un message
def recevoir_message(socket_client):
    try:
        taille_message_bytes = recevoir_exactement(socket_client, 4)
        if not taille_message_bytes:
            return None
        taille_message = struct.unpack('!I', taille_message_bytes)[0]
        donnees = recevoir_exactement(socket_client, taille_message)
        return donnees.decode('utf-8') if donnees else None
    except Exception as e:
        if isinstance(e, ConnectionError):
            pass  # Silencier les erreurs de fermeture de connexion
        else:
            print(f"Erreur lors de la réception du message : {e}")
        return None

# Fonction pour envoyer un message à un socket
def envoyer_message(socket_client, message):
    try:
        message_bytes = message.encode('utf-8')
        taille_message = struct.pack('!I', len(message_bytes))
        socket_client.sendall(taille_message + message_bytes)
    except Exception as e:
        print(f"Erreur lors de l'envoi du message : {e}")

# Implémentation de l'attente exponentielle dans la fonction de connexion
def essayer_connexion_exponentielle(machine, port, retries=5, temps_attente_base=1):
    socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for i in range(retries):
        try:
            socket_client.connect((machine, port))
            print(f"Connexion réussie avec {machine} sur le port {port} après {i+1} essai(s).")   
            return socket_client
        except Exception as e:
            print(f"Erreur lors de la connexion avec {machine} sur le port {port} : {e}. Nouvel essai ({i+1}/{retries})...")
            temps_attente = temps_attente_base * (2 ** i)  # Attente exponentielle
            time.sleep(temps_attente)
    print(f"Impossible de se connecter avec {machine} sur le port {port} après {retries} essais.")
    return None

# Connecter aux machines dans une phase spécifique
def connecter_phase(machine, port, dict_conn, phase):
    socket_client = essayer_connexion_exponentielle(machine, port)
    if socket_client:
        dict_conn[machine] = socket_client
        thread = threading.Thread(target=gerer_reception, args=(machine, socket_client, phase))   
        thread.start()
        threads_reception.append(thread)

# Connecter aux machines pour la phase 1
def connecter_phase_1():
    for machine in machines:
        connecter_phase(machine, PORT1, conn_phase1, 1)

# Envoyer les messages à chaque machine pour la Phase 1
def envoyer_messages_phase_1():
    machines_json = json.dumps(machines)
    messages_specifiques = ["bonjour", "hello", "hola", "hi"]

    # Envoyer la liste des machines connectées à chaque machine
    for machine, socket_client in conn_phase1.items():
        envoyer_message(socket_client, machines_json)
        print(f"Liste des machines envoyée à {machine}")

    # Envoyer les messages spécifiques
    for index, message in enumerate(messages_specifiques):
        machine_dest = machines[index % len(machines)]
        try:
            socket_client = conn_phase1[machine_dest]
            envoyer_message(socket_client, message)
            print(f"Envoyé '{message}' à {machine_dest}")
        except Exception as e:
            print(f"Erreur lors de l'envoi de '{message}' à {machine_dest} : {e}")

    # Envoyer 'FIN PHASE 1' pour indiquer la fin de la phase de mappage
    for machine, socket_client in conn_phase1.items():
        envoyer_message(socket_client, "FIN PHASE 1")
        print(f"Envoyé 'FIN PHASE 1' à {machine}")

# Fonction pour gérer la réception des messages pour chaque phase
def gerer_reception(machine, socket_client, phase):
    try:
        while True:
            message_recu = recevoir_message(socket_client)
            if not message_recu:
                break

            if phase == 1 and message_recu == "OK FIN PHASE 1":
                with lock:
                    tab_fin_phase_1.append(machine)
                    print(f"Reçu 'OK FIN PHASE 1' de {machine}")
                    if len(tab_fin_phase_1) == len(machines):
                        semaphore_phase_1.release()  # Libérer le sémaphore pour démarrer la Phase 2
            elif phase == 2 and message_recu == "FIN PHASE 2":
                with lock:
                    tab_fin_phase_2.append(machine)
                    print(f"Reçu 'FIN PHASE 2' de {machine}")
                    if len(tab_fin_phase_2) == len(machines):
                        semaphore_phase_2.release()  # Libérer le sémaphore pour démarrer la Phase 3
            elif phase == 3 and message_recu.startswith("{"):  # Résultat de la Phase 3 (Réduction)
                with lock:
                    resultats_reduction[machine] = json.loads(message_recu)
                    tab_fin_phase_3.append(machine)
                    print(f"Reçu résultat de réduction de {machine}")
                    if len(tab_fin_phase_3) == len(machines):
                        semaphore_phase_3.release()  # Libérer le sémaphore pour démarrer la Phase 4
            elif phase == 4 and message_recu == "FIN PHASE 4":
                with lock:
                    tab_fin_phase_4.append(machine)
                    print(f"Reçu 'FIN PHASE 4' de {machine}")
                    if len(tab_fin_phase_4) == len(machines):
                        semaphore_phase_4.release()
                break
            else:
                pass  # Vous pouvez gérer d'autres messages si nécessaire
    except Exception as e:
        print(f"Erreur lors de la réception pour {machine} en Phase {phase} : {e}")
        socket_client.close()
        socket_client = essayer_connexion_exponentielle(machine, PORT1 if phase == 1 else (PORT2 if phase == 2 else (PORT3 if phase == 3 else PORT4)))
        if socket_client:
            gerer_reception(machine, socket_client, phase)

# Fonction pour gérer le serveur pour chaque phase
def gerer_serveur_phase(port, fonction_handler, phase):
    serveur_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serveur_socket.bind(('0.0.0.0', port))
    serveur_socket.listen(len(machines))
    phase_num = port - 3465
    print(f"PHASE {phase_num} : Le serveur écoute sur le port {port}...")
    while True:
        socket_client, adresse_client = serveur_socket.accept()
        thread = threading.Thread(target=fonction_handler, args=(adresse_client[0], socket_client, phase))
        thread.start()
        threads_reception.append(thread)

# Fonction pour démarrer la Phase 2 (Shuffle)
def demarrer_phase_2():
    semaphore_phase_1.acquire()  # Attendre que la Phase 1 se termine
    print("Toutes les machines ont terminé la PHASE 1. Démarrage de la PHASE 2.")
    time.sleep(5)  # Pause de 5 secondes

    # Connecter à chaque machine dans la phase 2
    for machine in machines:
        connecter_phase(machine, PORT2, conn_phase2, 2)

    time.sleep(5)  # Pause pour établir les connexions

    # Envoyer 'GO PHASE 2' à chaque machine pour démarrer la phase de Shuffle
    for machine, socket_client in conn_phase2.items():
        envoyer_message(socket_client, "GO PHASE 2")
        print(f"Envoyé 'GO PHASE 2' à {machine}")

# Fonction pour démarrer la Phase 3 (Réduction)
def demarrer_phase_3():
    semaphore_phase_2.acquire()  # Attendre que la Phase 2 se termine
    print("Toutes les machines ont terminé la PHASE 2. Démarrage de la PHASE 3.")
    time.sleep(5)  # Pause de 5 secondes

    # Connecter à chaque machine dans la phase 3
    for machine in machines:
        connecter_phase(machine, PORT3, conn_phase3, 3)

    time.sleep(5)  # Pause pour établir les connexions

    # Envoyer 'GO PHASE 3' à chaque machine pour démarrer la phase de Réduction
    for machine, socket_client in conn_phase3.items():
        envoyer_message(socket_client, "GO PHASE 3")
        print(f"Envoyé 'GO PHASE 3' à {machine}")

# Fonction pour démarrer la Phase 4 (Consolidation et Finalisation)
def demarrer_phase_4():
    semaphore_phase_3.acquire()  # Attendre que la Phase 3 se termine
    print("Toutes les machines ont terminé la PHASE 3. Démarrage de la PHASE 4.")
    time.sleep(5)  # Pause de 5 secondes

    # Générer un fichier unique sans doublons
    generer_fichier_unique()

    # Connecter à chaque machine dans la phase 4
    for machine in machines:
        connecter_phase(machine, PORT4, conn_phase4, 4)

    time.sleep(5)  # Pause pour établir les connexions

    # Envoyer 'GO PHASE 4' à chaque machine pour finaliser
    for machine, socket_client in conn_phase4.items():
        envoyer_message(socket_client, "GO PHASE 4")
        print(f"Envoyé 'GO PHASE 4' à {machine}")

    semaphore_phase_4.acquire()  # Attendre que toutes les machines terminent la Phase 4
    print("Toutes les machines ont terminé la PHASE 4.")
    print("Communication terminée.")

# Fonction pour générer un fichier unique de résultats
def generer_fichier_unique():
    print("Génération du fichier unique de résultats...")
    # Combiner tous les résultats dans un seul dictionnaire
    resultat_combine = defaultdict(int)
    for resultat in resultats_reduction.values():
        for mot, compte in resultat.items():
            resultat_combine[mot] += compte

    # Convertir en dict
    resultat_unique = dict(resultat_combine)

    # Sauvegarder le résultat dans un fichier unique
    with open('resultat_unique.txt', 'w') as f:
        json.dump(resultat_unique, f, indent=4)

    print("Fichier unique généré : resultat_unique.txt")

# Flux principal
def main():
    # Démarrer les threads pour gérer les connexions entrantes dans chaque phase
    thread_serveur_phase1 = threading.Thread(target=gerer_serveur_phase, args=(PORT1, gerer_reception, 1))
    thread_serveur_phase1.start()
    threads_reception.append(thread_serveur_phase1)

    thread_serveur_phase2 = threading.Thread(target=gerer_serveur_phase, args=(PORT2, gerer_reception, 2))
    thread_serveur_phase2.start()
    threads_reception.append(thread_serveur_phase2)

    thread_serveur_phase3 = threading.Thread(target=gerer_serveur_phase, args=(PORT3, gerer_reception, 3))
    thread_serveur_phase3.start()
    threads_reception.append(thread_serveur_phase3)

    thread_serveur_phase4 = threading.Thread(target=gerer_serveur_phase, args=(PORT4, gerer_reception, 4))
    thread_serveur_phase4.start()
    threads_reception.append(thread_serveur_phase4)

    # Connecter aux machines dans la phase 1
    connecter_phase_1()

    # Envoyer les messages pour la phase 1
    envoyer_messages_phase_1()

    # Démarrer les phases dans des threads séparés pour utiliser les sémaphores
    thread_phase_2 = threading.Thread(target=demarrer_phase_2)
    thread_phase_3 = threading.Thread(target=demarrer_phase_3)
    thread_phase_4 = threading.Thread(target=demarrer_phase_4)

    thread_phase_2.start()
    thread_phase_3.start()
    thread_phase_4.start()

    # Attendre que tous les threads terminent
    thread_phase_2.join()
    thread_phase_3.join()
    thread_phase_4.join()

    for thread in threads_reception:
        thread.join()

    print("Tous les threads ont terminé.")

if __name__ == "__main__":
    main()
