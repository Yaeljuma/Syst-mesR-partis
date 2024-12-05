#!/bin/bash
set -e  # Detener la ejecución si ocurre un error

login="yjuarez-24"
localFolder="/mnt/c/Users/YAEL/OneDrive/Documentos/Sistemas_repartidos/dossierAdeployer"
remoteFolder="/cal/exterieurs/yjuarez-24/dossierAdeployer"

# Leer la lista de máquinas, eliminando caracteres de retorno de carro y espacios
mapfile -t computers < <(grep -v '^$' machines.txt | tr -d '\r' | tr -d ' ')

# Lista de puertos a liberar
ports=(5000 5001 5002 5003 5101 5102 5103 5201 3466 3467 3468 3469)

for c in "${computers[@]}"; do
    if [[ -z "$c" ]]; then
        continue
    fi

    echo "Desplegando en $c..."

    # Construir el comando para matar procesos en los puertos especificados
    kill_ports_cmd="lsof -i :5000 -i :5001 -i :5002 -i :5003 | awk 'NR>1 {print \$2}' | xargs -r kill -9; "
    for port in "${ports[@]}"; do
        kill_ports_cmd+="fuser -k ${port}/tcp || true; "
    done

    # Matar procesos que usen los puertos para evitar conflictos
    ssh -tt "$login@$c" "$kill_ports_cmd; wait; sleep 2;"  # Aumentar el tiempo de espera para liberar puertos

    # Crear el directorio remoto
    ssh -tt "$login@$c" "mkdir -p $remoteFolder; wait;"

    # Copiar solo los archivos necesarios, excluyendo envoyeur.py
    rsync -av --exclude 'envoyeur.py' "$localFolder/" "$login@$c:$remoteFolder/"

    # Ejecutar el script en la máquina remota
    ssh -tt "$login@$c" "cd $remoteFolder; python3 script.py; wait;" &
done

wait

echo "Despliegue completado. Los scripts remotos han terminado."
