#!/bin/bash

bucket="INFORMAR"
subpasta_sequencias="sequencias-fasta"
subpasta_dados="dados-containers"

#puxando as sequencias do bucket no s3
aws s3 cp --recursive s3://$bucket/$subpasta_sequencias/${INPUT_SET}K/ ./sequencias/

if [[ "$AWS_EXECUTION_ENV" == *"AWS_ECS_FARGATE"* ]]; then
    ambiente="FARGATE"
else
    ambiente="EC2"
fi

#capturando hora e dia iniciais a fum de gerar uma identificacao unica
hora_inicial=$(date +"%H:%M:%S")
dia_inicial=$(date +"%d_%m_%Y")

#arquivo de dados de cada alinhamento
touch dados-$ambiente-$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}.csv
echo "dia; hora; arquivo1; tamanho1; arquivo2; tamanho2; max_mem(mb); tempo_max_mem(s); tempo_total;" >> dados-$ambiente-$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}.csv

#monitorando a execucao do masa
python3 ./rprof.py -m -g "./masa.sh $THREADS dados-$ambiente-$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}.csv"

#criando pasta no bucket s3 para essa execucao
aws s3api put-object --bucket $bucket --key $subpasta_dados/$ambiente/$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}/

#enviando arquivo de dados ao s3
aws s3 cp ./dados-$ambiente-$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}.csv s3://$bucket/$subpasta_dados/$ambiente/$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}/

#programa que gera graficos de consumo de memoria
python3 ./rprof-plotter.py -m -i . -t "$ambiente-$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}"

mv memory.csv memory-${INPUT_SET}K-t${THREADS}.csv

#enviando dados e graficos de consumo de memoria dessa execucao ao bucket
aws s3 cp ./memory-${INPUT_SET}K-t${THREADS}.csv s3://$bucket/$subpasta_dados/$ambiente/$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}/

rm memory-${INPUT_SET}K-t${THREADS}.csv

find . -name "*.png" -exec aws s3 cp {} s3://$bucket/$subpasta_dados/$ambiente/$dia_inicial-$hora_inicial-r${RODADA}-${INPUT_SET}K-t${THREADS}/ \;

#capturando os metadados do container
task_metadata=$(curl -s ${ECS_CONTAINER_METADATA_URI_V4}/task)

task_arn=$(echo $task_metadata | jq -r '.TaskARN')
cluster=$(echo $task_metadata | jq -r '.Cluster')

#mensagem final para gatilho da funcao_lambda_1
echo "FIM:{\"task_arn\": \"$task_arn\",\"cluster\": \"$cluster\",\"ambiente\": \"$ambiente\",\"dia_inicial\": \"$dia_inicial\",\"hora_inicial\": \"$hora_inicial\",\"input_set\": \"$INPUT_SET\",\"rodada\": \"$RODADA\",\"threads\": \"$THREADS\"}"