#!/bin/bash

# Recebendo variáveis de ambiente do Kubernetes
bucket=${BUCKET:-"bucket-saramcav"}
subpasta_sequencias=${SUBPASTA_SEQUENCIAS:-"sequencias-fasta"}
subpasta_resultados=${SUBPASTA_RESULTADOS:-"dados-containers"}
ambiente=${AMBIENTE:-"EKS"}
THREADS=${THREADS:-16}
INPUT_SET=${INPUT_SET:-10}
CONTAINER_ID=${CONTAINER_ID:-0}
TOTAL_CONTAINERS=${TOTAL_CONTAINERS:-1}

echo "=== MASA-OpenMP no EKS ==="
echo "Configuração:"
echo "  - Total de containers: ${TOTAL_CONTAINERS}"
echo "  - Container ID: ${CONTAINER_ID}"
echo "  - Threads por container: ${THREADS}"
echo "  - Dataset: ${INPUT_SET}K sequências"
echo "  - Ambiente: ${ambiente}"
echo "=========================="

# Configurando credenciais AWS a partir das variáveis de ambiente
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

# Criando diretório de sequências
mkdir -p ./sequencias

echo "Baixando sequências do S3..."
# puxando as sequencias do bucket no s3
aws s3 cp --recursive s3://$bucket/$subpasta_sequencias/${INPUT_SET}K/ ./sequencias/

# Verificando se o download foi bem-sucedido
if [ ! "$(ls -A ./sequencias/)" ]; then
    echo "ERRO: Não foi possível baixar sequências do S3!"
    echo "Bucket: s3://$bucket/$subpasta_sequencias/${INPUT_SET}K/"
    exit 1
fi

echo "Sequências baixadas com sucesso!"

hora_inicial=$(date +"%H:%M:%S")
dia_inicial=$(date +"%d_%m_%Y")

# Criando nome do arquivo que inclui informações de paralelização
if [ "$TOTAL_CONTAINERS" -eq 1 ]; then
    # 1 container
    arquivo_dados="dados-$ambiente-$dia_inicial-$hora_inicial-${INPUT_SET}K-1c-t$THREADS.csv"
else
    # Múltiplos containers
    arquivo_dados="dados-$ambiente-$dia_inicial-$hora_inicial-${INPUT_SET}K-${TOTAL_CONTAINERS}c-t${THREADS}-id${CONTAINER_ID}.csv"
fi

echo "Arquivo de resultados: $arquivo_dados"

# criando e adicionando colunas do arquivo de dados de cada alinhamento
touch $arquivo_dados
echo "rodada;container_id;dia;hora;arquivo1;tamanho1;arquivo2;tamanho2;tempo_total;" >> $arquivo_dados

# Definindo RODADA para identificar a configuração
if [ "$TOTAL_CONTAINERS" -eq 1 ]; then
    RODADA="1c-${THREADS}t"
else
    RODADA="${TOTAL_CONTAINERS}c-${THREADS}t"
fi

export RODADA

echo "Iniciando processamento MASA..."
# executando o script que executa a sequencia de alinhamentos
./masa.sh $THREADS $arquivo_dados $TOTAL_CONTAINERS $CONTAINER_ID

# Criando estrutura de pasta no S3 baseada na configuração
if [ "$TOTAL_CONTAINERS" -eq 1 ]; then
    pasta_s3="$subpasta_resultados/$ambiente/1container-${THREADS}threads/${INPUT_SET}K/$dia_inicial-$hora_inicial/"
else
    pasta_s3="$subpasta_resultados/$ambiente/${TOTAL_CONTAINERS}containers-${THREADS}threads/${INPUT_SET}K/$dia_inicial-$hora_inicial/"
fi

echo "Criando pasta no S3: $pasta_s3"
# criando pasta no s3 para essa execucao
aws s3api put-object --bucket $bucket --key $pasta_s3

echo "Enviando resultados para S3..."
# enviando arquivo de dados ao s3 para a pasta criada acima
aws s3 cp ./$arquivo_dados s3://$bucket/$pasta_s3

# Capturando metadados do Kubernetes (equivalente ao ECS metadata)
HOSTNAME=$(hostname)
NAMESPACE=$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace 2>/dev/null || echo "default")
NODE_NAME=${KUBERNETES_NODE_NAME:-$(kubectl get pod $HOSTNAME -o jsonpath='{.spec.nodeName}' 2>/dev/null || echo "unknown")}

echo "=== Metadados da Execução ==="
echo "Pod: $HOSTNAME"
echo "Namespace: $NAMESPACE" 
echo "Node: $NODE_NAME"
echo "Container ID: $CONTAINER_ID"
echo "Configuração: $RODADA"
echo "Dataset: ${INPUT_SET}K"
echo "Arquivo gerado: $arquivo_dados"
echo "Local S3: s3://$bucket/$pasta_s3$arquivo_dados"
echo "============================="

echo "✅ Execução finalizada com sucesso!"
