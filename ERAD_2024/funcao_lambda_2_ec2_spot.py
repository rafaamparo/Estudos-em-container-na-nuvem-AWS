import boto3
import botocore
import csv
from datetime import timedelta, datetime
import io

# função lambda 2 utilizada no caso ECS + EC2 Spot
# caso esteja interessado em ECS + EC2 Sob Demanda ou ECS + AWS Fargate, acesse "funcao_lambda_2_ec2_sd_e_fargate.py"

#para executa-la, e necessario definir as seguintes permissoes para a funcao alem dos que ja vem:

        # {
        #     "Effect": "Allow",
        #     "Action": [
        #         "s3:ListBucket",
        #         "s3:GetObject",
        #         "s3:PutObject",
        #         "s3:DeleteObject"
        #     ],
        #     "Resource": INFORMAR
        # },
        # {
        #     "Effect": "Allow",
        #     "Action": "ec2:DescribeSpotPriceHistory",
        #     "Resource": INFORMAR
        # }

#Obs.: no campo "INFORMAR", pode-se adicionar um "*" para que valha para qualquer recurso


vals_inputs = [200, 300, 400]
vals_containers = [1, 2, 4]

def obtem_preco_spot(tipo_instancia, regiao, timestamp_str):
    timestamp = datetime.strptime(timestamp_str, '%d_%m_%Y-%H:%M:%S')
    
    ec2_client = boto3.client('ec2', region_name=regiao)
    
    resp = ec2_client.describe_spot_price_history(
        InstanceTypes=[tipo_instancia],
        ProductDescriptions=['Linux/UNIX'],
        StartTime=timestamp,
        EndTime=timestamp
    )
    
    if 'SpotPriceHistory' in resp and len(resp['SpotPriceHistory']) > 0:
        menor_preco = min(float(item['SpotPrice']) for item in resp['SpotPriceHistory'])
        return menor_preco
    return 0

def ler_arquivo_s3(bucket, caminho_arquivo):
    s3 = boto3.client('s3')
    try:
        resposta = s3.get_object(Bucket=bucket, Key=caminho_arquivo)
        conteudo = resposta['Body'].read().decode('utf-8').strip()
        return conteudo
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao acessar o arquivo {caminho_arquivo}: {e}')
        return None

def parse_tempo(tempo_str):
    partes = tempo_str.split(':')
    horas = int(partes[0])
    minutos = int(partes[1])
    segundos = float(partes[2])
    return timedelta(hours=horas, minutes=minutos, seconds=segundos)

def listar_arquivos(bucket, prefixo, sufixo):
    s3 = boto3.client('s3')
    arquivos = []
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefixo):
            if 'Contents' in page:
                for item in page['Contents']:
                    chave = item['Key']
                    if chave.endswith(sufixo):
                        arquivos.append(chave)
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao listar os arquivos no bucket {bucket}: {e}')
    return arquivos

def formatar_timedelta(td):
    total_segundos = td.total_seconds()
    horas = int(total_segundos // 3600)
    minutos = int((total_segundos % 3600) // 60)
    segundos = total_segundos % 60
    return f"{horas:02}:{minutos:02}:{segundos:05.2f}"

def extrair_timestamp_str(nome_arquivo):
    partes = nome_arquivo.split('/')[-1].split('-')
    return f'{partes[2]}-{partes[3]}'

def processar_arquivos_tempo_e_custo_s3(bucket, prefixo, tipo_instancia, regiao):
    pref = prefixo
    resultados = {}

    with open('/tmp/precos_spot.txt', 'w') as arquivo_precos:
        for input_set in vals_inputs:
            for container in vals_containers:
                prefixo_config = f'{pref}{container}c-{input_set}K/'
                tempos = []
                custos = []

                sufixo_tempo = f'.txt'
                arquivos_tempo = listar_arquivos(bucket, prefixo_config, sufixo_tempo)

                for caminho_arquivo in arquivos_tempo:
                    conteudo = ler_arquivo_s3(bucket, caminho_arquivo)
                    if conteudo is not None:
                        tempo = parse_tempo(conteudo)
                        tempos.append(tempo)

                        timestamp_str = extrair_timestamp_str(caminho_arquivo)

                        preco_spot = obtem_preco_spot(tipo_instancia, regiao, timestamp_str)
                        custo = (preco_spot / 3600) * tempo.total_seconds()
                        custos.append(custo)

                        #registrando preco spot para aquela execucao
                        arquivo_precos.write(f'{container}containers-{input_set}K:: Custo: {preco_spot} USD/h\n')

                if tempos and custos:
                    media_tempo = sum(tempos, timedelta()) / len(tempos)
                    
                    if 0 in custos:
                        media_custo = 0
                    else:
                        media_custo = sum(custos) / len(custos)

                    resultados[f'{container}containers-{input_set}K'] = (
                        formatar_timedelta(media_tempo), 
                        media_tempo.total_seconds(), 
                        media_custo
                    )

        print("Resultados calculados:", resultados)

    return resultados


def agrupar_csvs(bucket, pref, arq):
    s3 = boto3.client('s3')
    dados_totais = []

    for input_set in vals_inputs:
        for quant_containers in vals_containers:
            prefixo = f'{pref}{quant_containers}c-{input_set}K/'
            
            sufixo = '.csv'
            arquivos_csv = listar_arquivos(bucket, prefixo, sufixo)
            
            for arquivo in arquivos_csv:
                obj = s3.get_object(Bucket=bucket, Key=arquivo)
                conteudo = obj['Body'].read().decode('utf-8')
                
                csv_reader = csv.reader(io.StringIO(conteudo), delimiter=';')
                cabecalho = next(csv_reader)  # pula cabeçalho
                dados_totais.extend(list(csv_reader))

                #s3.delete_object(Bucket=bucket, Key=arquivo)
    
    dados_totais.sort(key=lambda x: (
        datetime.strptime(x[2], '%d/%m/%Y'),  # Converte o campo 'dia'
        datetime.strptime(x[3], '%H:%M:%S')   # Converte o campo 'hora'
    ))

    with open(arq, mode='w', newline='', encoding='utf-8') as file:
        csv_writer = csv.writer(file, delimiter=';')
        cabecalho = ['rodada', 'container', 'dia', 'hora', 'arquivo1', 'tamanho1', 'arquivo2', 'tamanho2', 'tempo_total']
        csv_writer.writerow(cabecalho)
        csv_writer.writerows(dados_totais)
    
    print(f'Arquivo CSV consolidado salvo em {arq}.')

def salvar_resultados_em_arquivo(resultados, nome_arquivo):
    with open(nome_arquivo, 'w') as file:
        for chave, (tempo_formatado, tempo_segundos, custo_medio) in resultados.items():
            file.write(f'{chave}:: Tempo médio: {tempo_formatado}, Custo médio: ${custo_medio:.5f} USD\n')

def enviar_arquivo_s3(bucket, caminho_arquivo, nome_arquivo):
    s3 = boto3.client('s3')
    try:
        s3.upload_file(nome_arquivo, bucket, caminho_arquivo)
        print(f'Arquivo {nome_arquivo} enviado para {caminho_arquivo} no bucket {bucket}.')
        
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao enviar o arquivo {nome_arquivo} para {caminho_arquivo}: {e}')
        
def lambda_handler(event, context):
    ambiente = event.get('ambiente', 'EC2')
    tipo_instancia = 'c7g.4xlarge'
    regiao = 'us-east-1'

    bucket = 'bucket-saramcav'
    prefixo = f'dados-containers/{ambiente}/'

    resultados = processar_arquivos_tempo_e_custo_s3(bucket, prefixo, tipo_instancia, regiao)
    
    arq_tempo_custo = f'/tmp/TEMPO_CUSTO_MEDIOS_{ambiente}.txt'
    caminho_tempo_custo_s3 = f'dados-containers/{ambiente}/TEMPO_CUSTO_MEDIOS_{ambiente}.txt'
    
    arq_dados = f'/tmp/DADOS_AGRUPADOS_{ambiente}.csv'
    caminho_dados_S3 = f'dados-containers/{ambiente}/DADOS_AGRUPADOS_{ambiente}.csv'

    caminho_preco_spot = f'dados-containers/{ambiente}/precos_spot.txt'

    salvar_resultados_em_arquivo(resultados, arq_tempo_custo)
    enviar_arquivo_s3(bucket, caminho_tempo_custo_s3, arq_tempo_custo)

    agrupar_csvs(bucket, prefixo, arq_dados)
    enviar_arquivo_s3(bucket, caminho_dados_S3, arq_dados)

    enviar_arquivo_s3(bucket, caminho_preco_spot, '/tmp/precos_spot.txt')