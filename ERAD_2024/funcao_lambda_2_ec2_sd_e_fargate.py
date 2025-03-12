import boto3
import botocore
import csv
from datetime import timedelta
from datetime import datetime
import io

# função lambda 2 utilizada nos seguintes casos:
# ECS + EC2 Sob Demanda 
# ECS + AWS Fargate
# caso esteja interessado em ECS + EC2 Spot, acesse "funcao_lambda_2_ec2_spot.py"


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
    # }

#Obs.: no campo "INFORMAR", pode-se adicionar um "*" para que valha para qualquer recurso


vals_inputs=[200, 300, 400]
vals_containers=[1, 2, 4]

def ler_arquivo_s3(bucket, caminho_arquivo, csv=False):
    s3 = boto3.client('s3')
    try:
        resposta = s3.get_object(Bucket=bucket, Key=caminho_arquivo)
        conteudo = resposta['Body'].read().decode('utf-8').strip()
        if csv:
            return conteudo.splitlines()[1:]
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

def calcular_media(tempos):
    return sum(tempos, timedelta()) / len(tempos)

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

def processar_arquivos_tempo_s3(bucket, prefixo):
    pref = prefixo
    resultados = {}
    for input_set in vals_inputs:
        for container in vals_containers:
            prefixo = f'{pref}{container}c-{input_set}K/'
            tempos = []

            print("pref", prefixo)

            sufixo_tempo = f'.txt'
            
            arquivos_tempo = listar_arquivos(bucket, prefixo, sufixo_tempo)
            for caminho_arquivo in arquivos_tempo:
                conteudo = ler_arquivo_s3(bucket, caminho_arquivo)
                if conteudo is not None:
                    tempos.append(parse_tempo(conteudo))
                
            if tempos != []:
                media_tempo = calcular_media(tempos)
                resultados[f'{container}containers-{input_set}K'] = (formatar_timedelta(media_tempo), media_tempo.total_seconds())
    
    print("aqui os resultados")
    print(resultados)

    return resultados

def salvar_resultados_em_arquivo(resultados, nome_arquivo, ambiente):
    with open(nome_arquivo, 'w') as file:
        if ambiente == "EC2":
            #'c7g.4xlarge US East (N. Virginia)' 
            preco_por_hora = 0.58
            for chave, (valor_formatado, valor_segundos) in resultados.items():
                if valor_segundos < 60:
                    valor_segundos = 60
                custo = (preco_por_hora / 3600) * valor_segundos

                file.write(f'{chave}:: Tempo: {valor_formatado}, Custo estimado: ${custo:.5f} USD\n')
        else:
            v_cpu = 8
            memoria = 16
            preco_v_cpu_por_hora = 0.03238 
            preco_memoria_por_hora = 0.00356 
            for chave, (valor_formatado, valor_segundos) in resultados.items():
                if valor_segundos < 60:
                    valor_segundos = 60
                custo_v_cpu = (preco_v_cpu_por_hora / 3600) * v_cpu * valor_segundos
                custo_memoria = (preco_memoria_por_hora / 3600) * memoria * valor_segundos
                custo_total = custo_v_cpu + custo_memoria

                file.write(f'{chave}:: Tempo: {valor_formatado}, Custo estimado: ${custo_total:.5f} USD\n')

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


def enviar_arquivo_s3(bucket, caminho_arquivo, nome_arquivo):
    s3 = boto3.client('s3')
    try:
        s3.upload_file(nome_arquivo, bucket, caminho_arquivo)
        print(f'Arquivo {nome_arquivo} enviado para {caminho_arquivo} no bucket {bucket}.')
        
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao enviar o arquivo {nome_arquivo} para {caminho_arquivo}: {e}')


def lambda_handler(event, context):
    ambiente = event.get('ambiente')
    bucket = 'INFORMAR'
    subpasta_dados="dados-containers"
    prefixo = f'{subpasta_dados}/{ambiente}/'
    
    resultados = processar_arquivos_tempo_s3(bucket, prefixo)
    
    arq_tempo_custo = f'/tmp/TEMPO_CUSTO_MEDIOS_{ambiente}.txt'
    caminho_tempo_custo_s3 = f'{subpasta_dados}/{ambiente}/TEMPO_CUSTO_MEDIOS_{ambiente}.txt'
    
    arq_dados = f'/tmp/DADOS_AGRUPADOS_{ambiente}.csv'
    caminho_dados_S3 = f'{subpasta_dados}/{ambiente}/DADOS_AGRUPADOS_{ambiente}.csv'

    salvar_resultados_em_arquivo(resultados, arq_tempo_custo, ambiente)
    enviar_arquivo_s3(bucket, caminho_tempo_custo_s3, arq_tempo_custo)

    agrupar_csvs(bucket, prefixo, arq_dados)
    enviar_arquivo_s3(bucket, caminho_dados_S3, arq_dados)