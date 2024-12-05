➜  dossierAdeployer cat envoyeur.py 
import socket
import json
import struct
import threading
from collections import defaultdict
import time

# Ports pour chaque phase
PORT1 = 3466
PORT2 = 3467
PORT3 = 3468
PORT4 = 3469

# Lire les adresses des machines depuis le fichier machines.txt
with open('machines.txt', 'r') as file:
    machines = [line.strip() for line in file.readlines() if line.strip()]

# Variables globales
tab_fin_phase_1 = []
tab_fin_phase_2 = []
tab_fin_phase_3 = []
tab_fin_phase_4 = []
resultats_reduction = {}
lock = threading.Lock()
semaphore_phase_1 = threading.Semaphore(0)
semaphore_phase_2 = threading.Semaphore(0)
semaphore_phase_3 = threading.Semaphore(0)
semaphore_phase_4 = threading.Semaphore(0)

# Fonction pour recevoir un nombre exact d'octets
def recevoir_exactement(client_socket, n):
    data = b''
    while len(data) < n:
        packet = client_socket.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

# Fonction pour recevoir un message complet
def recevoir_message(client_socket):
    try:
        taille_message_bytes = recevoir_exactement(client_socket, 4)
        if not taille_message_bytes:
            return None
        taille_message = struct.unpack('!I', taille_message_bytes)[0]
        donnees = recevoir_exactement(client_socket, taille_message)
        return donnees.decode('utf-8') if donnees else None
    except Exception as e:
        print(f"Erreur lors de la réception du message : {e}")
        return None

# Fonction pour envoyer un message à un socket
def envoyer_message(client_socket, message):
    try:
        message_bytes = message.encode('utf-8')
        taille_message = struct.pack('!I', len(message_bytes))
        client_socket.sendall(taille_message + message_bytes)
    except Exception as e:
        print(f"Erreur lors de l'envoi du message : {e}")

# Phase 1 : Envoyer les données initiales
def envoyer_donnees_phase_1():
    print("PHASE 1 : Début de l'envoi des données initiales aux machines.")
    # Assigner les fichiers aux machines
    fichiers = [
        "CC-MAIN-20230320144934-20230320174934-00404.warc.wet",
        "CC-MAIN-20230320144934-20230320174934-00405.warc.wet",
        "CC-MAIN-20230320144934-20230320174934-00406.warc.wet",
        "CC-MAIN-20230321002050-20230321032050-00460.warc.wet",
        "CC-MAIN-20230321002050-20230321032050-00472.warc.wet",
        "CC-MAIN-20230321002050-20230321032050-00486.warc.wet"
    ]

    fichiers_par_machine = defaultdict(list)
    for i, fichier in enumerate(fichiers):
        fichiers_par_machine[machines[i % len(machines)]].append(fichier)

    # Se connecter à chaque machine et envoyer les données initiales
    for machine in machines:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((machine, PORT1))
            data = {
                "machines": machines,
                "files": fichiers_par_machine[machine]
            }
            envoyer_message(client_socket, json.dumps(data))
            print(f"Données initiales envoyées à {machine}.")

            # Créer un thread pour gérer la réception de la confirmation
            thread = threading.Thread(target=gerer_reception_phase, args=(machine, client_socket, 1))
            thread.start()
        except Exception as e:
            print(f"Erreur lors de la connexion à {machine} en Phase 1 : {e}")

# Gérer la réception des messages par phase
def gerer_reception_phase(machine, client_socket, phase):
    try:
        while True:
            message_recu = recevoir_message(client_socket)
            if not message_recu:
                break

            if phase == 1 and message_recu == "OK FIN PHASE 1":
                with lock:
                    tab_fin_phase_1.append(machine)
                    print(f"Reçu 'OK FIN PHASE 1' de {machine}")
                    if len(tab_fin_phase_1) == len(machines):
                        semaphore_phase_1.release()
                break
            elif phase == 2 and message_recu == "FIN PHASE 2":
                with lock:
                    tab_fin_phase_2.append(machine)
                    print(f"Reçu 'FIN PHASE 2' de {machine}")
                    if len(tab_fin_phase_2) == len(machines):
                        semaphore_phase_2.release()
                break
            elif phase == 3 and message_recu.startswith("{"):
                with lock:
                    resultats_reduction[machine] = json.loads(message_recu)
                    tab_fin_phase_3.append(machine)
                    print(f"Reçu résultat de réduction de {machine}")
                    if len(tab_fin_phase_3) == len(machines):
                        semaphore_phase_3.release()
                break
            elif phase == 4 and message_recu == "FIN PHASE 4":
                with lock:
                    tab_fin_phase_4.append(machine)
                    print(f"Reçu 'FIN PHASE 4' de {machine}")
                    if len(tab_fin_phase_4) == len(machines):
                        semaphore_phase_4.release()
                break
            else:
                print(f"Message inattendu de {machine} en Phase {phase} : {message_recu}")        
    except Exception as e:
        print(f"Erreur lors de la gestion de la réception de {machine} en Phase {phase} : {e}")   

# Phase 2 : Shuffle
def demarrer_phase_2():
    semaphore_phase_1.acquire()
    print("Toutes les machines ont terminé la PHASE 1. Début de la PHASE 2.")

    time.sleep(3)

    for machine in machines:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((machine, PORT2))
            envoyer_message(client_socket, "GO PHASE 2")
            print(f"Envoyé 'GO PHASE 2' à {machine}.")
            thread = threading.Thread(target=gerer_reception_phase, args=(machine, client_socket, 2))
            thread.start()
        except Exception as e:
            print(f"Erreur lors de la connexion à {machine} en Phase 2 : {e}")

# Phase 3 : Réduction
def demarrer_phase_3():
    semaphore_phase_2.acquire()
    print("Toutes les machines ont terminé la PHASE 2. Début de la PHASE 3.")

    time.sleep(3)

    for machine in machines:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((machine, PORT3))
            envoyer_message(client_socket, "GO PHASE 3")
            print(f"Envoyé 'GO PHASE 3' à {machine}.")
            thread = threading.Thread(target=gerer_reception_phase, args=(machine, client_socket, 3))
            thread.start()
        except Exception as e:
            print(f"Erreur lors de la connexion à {machine} en Phase 3 : {e}")

# Phase 4 : Finalisation
def demarrer_phase_4():
    semaphore_phase_3.acquire()
    print("Toutes les machines ont terminé la PHASE 3. Début de la PHASE 4.")

    time.sleep(3)

    resultats_finaux = defaultdict(int)
    for resultat in resultats_reduction.values():
        for mot, compteur in resultat.items():
            resultats_finaux[mot] += compteur

    with open("resultat_unique.txt", "w", encoding="utf-8") as f:
        json.dump(dict(resultats_finaux), f, ensure_ascii=False, indent=4)

    print("Fichier unique généré : resultat_unique.txt")

    for machine in machines:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((machine, PORT4))
            envoyer_message(client_socket, "GO PHASE 4")
            print(f"Envoyé 'GO PHASE 4' à {machine}.")
            thread = threading.Thread(target=gerer_reception_phase, args=(machine, client_socket, 4))
            thread.start()
        except Exception as e:
            print(f"Erreur lors de la connexion à {machine} en Phase 4 : {e}")

# Fonction principale
def main():
    envoyer_donnees_phase_1()
    demarrer_phase_2()
    demarrer_phase_3()
    demarrer_phase_4()
    print("Toutes les phases ont été complétées avec succès.")

if __name__ == "__main__":
    main()
