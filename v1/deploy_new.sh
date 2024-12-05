➜  dossierAdeployer cat deploy_new.sh                                                             
#!/bin/bash
set -e  # Arrêter l'exécution en cas d'erreur

login="yjuarez-24"
localFolder="/mnt/c/Users/YAEL/OneDrive/Documentos/Sistemas_repartidos/dossierAdeployer"
remoteFolder="/cal/exterieurs/yjuarez-24/dossierAdeployer"

# Lire la liste des machines, en supprimant les caractères de retour chariot et les espaces       
mapfile -t computers < <(grep -v '^$' machines.txt | tr -d '\r' | tr -d ' ')

# Liste des ports à libérer
ports=(5000 5001 5002 5003 5101 5102 5103 5201 3466 3467 3468 3469)

# Début du compteur de temps
start_time=$(date +%s)

for c in "${computers[@]}"; do
    if [[ -z "$c" ]]; then
        continue
    fi

    echo "Déploiement sur $c..."

    # Construire la commande pour tuer les processus sur les ports spécifiés
    kill_ports_cmd="lsof -i :5000 -i :5001 -i :5002 -i :5003 | awk 'NR>1 {print \$2}' | xargs -r kill -9; "
    for port in "${ports[@]}"; do
        kill_ports_cmd+="fuser -k ${port}/tcp || true; "
    done

    # Tuer les processus utilisant les ports pour éviter les conflits
    ssh -tt "$login@$c" "$kill_ports_cmd; wait; sleep 2;"  # Augmenter le temps d'attente pour libérer les ports

    # Créer le répertoire distant
    ssh -tt "$login@$c" "mkdir -p $remoteFolder; wait;"

    # Copier uniquement les fichiers nécessaires, en excluant envoyeur.py
    rsync -av --exclude 'envoyeur.py' "$localFolder/" "$login@$c:$remoteFolder/"

    # Exécuter le script sur la machine distante
    ssh -tt "$login@$c" "cd $remoteFolder; python3 script.py; wait;" &
done

wait

# Fin du compteur de temps
end_time=$(date +%s)
elapsed_time=$((end_time - start_time))

echo "Déploiement terminé. Les scripts distants ont fini."
echo "Temps total écoulé : ${elapsed_time} secondes."
