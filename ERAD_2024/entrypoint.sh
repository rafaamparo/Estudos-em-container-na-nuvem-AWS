#!/bin/bash

#Capturando os metadados do container
metadados_tarefa=$(curl -s ${ECS_CONTAINER_METADATA_URI_V4}/task)

arn_tarefa=$(echo $metadados_tarefa | jq -r '.TaskARN')
cluster=$(echo $metadados_tarefa | jq -r '.Cluster')

nome_bucket="INFORMAR"
subpasta_sequencias="sequencias-fasta"
subpasta_dados="dados-containers"

arn_container=$(curl -s $ECS_CONTAINER_METADATA_URI_V4 | jq -r '.ContainerARN')
nome_container=$(aws ecs describe-tasks --cluster $cluster --tasks $arn_tarefa --query "tasks[0].containers[?containerArn=='$arn_container'].name" --output text)

# containers nomeados como "container-0", "container-1", etc. Extrai apenas o número
id_container=$(echo $nome_container | awk -F'-' '{print $2}')

# Encontrando a quantidade de containers
nomes_containers=$(aws ecs describe-tasks --cluster $cluster --tasks $arn_tarefa --query "tasks[0].containers[].name" --output text)
max_id=0

for nome in $nomes_containers; do
    id=$(echo $nome | awk -F'-' '{print $2}')
    
    if [[ $id -gt $max_id ]]; then
        max_id=$id
    fi
done

quant_containers=$((max_id + 1))

#puxando as sequencias do bucket no s3
aws s3 cp --recursive s3://$nome_bucket/$subpasta_sequencias/${INPUT_SET}K/ ./sequencias/

if [[ "$AWS_EXECUTION_ENV" == *"AWS_ECS_FARGATE"* ]]; then
    ambiente="FARGATE"
else
    ambiente="EC2"
fi

# Pega o pullStartedAt da tarefa para criar uma identificação única
inicio_pull=$(aws ecs describe-tasks --cluster $cluster --tasks $arn_tarefa --query "tasks[0].pullStartedAt" --output text)
identificacao=$(date -d "@$inicio_pull" +"%d_%m_%Y-%H:%M:%S")

#arquivo de dados de cada alinhamento
touch dados-$ambiente-$identificacao-${INPUT_SET}K-r${RODADA}-c${id_container}.csv
echo "rodada;container;dia;hora;arquivo1;tamanho1;arquivo2;tamanho2;tempo_total" >> dados-$ambiente-$identificacao-${INPUT_SET}K-r${RODADA}-c${id_container}.csv

./masa.sh $THREADS dados-$ambiente-$identificacao-${INPUT_SET}K-r${RODADA}-c${id_container}.csv $quant_containers $id_container

#criando pasta no s3 para essa execucao nesse container
aws s3api put-object --bucket $nome_bucket --key $subpasta_dados/$ambiente/${quant_containers}c-${INPUT_SET}K/$identificacao-r${RODADA}/$nome_container/

#enviando arquivo de dados ao s3
aws s3 cp ./dados-$ambiente-$identificacao-${INPUT_SET}K-r${RODADA}-c${id_container}.csv s3://$nome_bucket/$subpasta_dados/$ambiente/${quant_containers}c-${INPUT_SET}K/$identificacao-r${RODADA}/$nome_container/

invocar_lambda() {
    if [ "$ambiente" == "EC2" ]; then
        nome_funcao_lambda="ERAD-trata-final-tarefa-EC2"
    else
        nome_funcao_lambda="ERAD-trata-final-tarefa-FARGATE"
    fi

    payload=$(jq -n \
        --arg arn_tarefa "$1" \
        --arg cluster "$2" \
        --arg ambiente "$3" \
        --arg identificacao "$4" \
        --arg input_set "$5" \
        --arg rodada "$6" \
        --arg quant_containers "$7" \
        '{
            arn_tarefa: $arn_tarefa,
            cluster: $cluster,
            ambiente: $ambiente,
            identificacao: $identificacao,
            input_set: $input_set,
            rodada: $rodada,
            quant_containers: $quant_containers
        }')

    aws lambda invoke \
        --function-name "$nome_funcao_lambda" \
        --invocation-type Event \
        --payload "$payload" \
        /dev/null

    if [ $? -eq 0 ]; then
        echo "Função Lambda invocada com sucesso para a tarefa: $arn_tarefa"
    else
        echo "Erro ao invocar a função Lambda"
    fi
}

# se for o container essencial, espera todos executarem
if [[ "$id_container" -eq 0 ]]; then
    echo "Container essencial chegou ao final, monitorando os outros containers..."

    while true; do
        todos_terminados=true
        for id in $(seq 1 $((quant_containers - 1))); do
            container_nome="container-$id"
            status_container=$(aws ecs describe-tasks --cluster $cluster --tasks $arn_tarefa --query "tasks[0].containers[?name=='$container_nome'].lastStatus" --output text)
            if [[ "$status_container" != "STOPPED" ]]; then
                todos_terminados=false
                break
            fi
        done
        
        if $todos_terminados; then
            echo "Todos os containers terminaram. Finalizando container essencial e chamando função de custo..."

            invocar_lambda "$arn_tarefa" "$cluster" "$ambiente" "$identificacao" "$INPUT_SET" "$RODADA" "$quant_containers"

            break
        fi
        
        sleep 2
    done
fi