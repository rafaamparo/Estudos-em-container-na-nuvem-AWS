
#para executa-la, e necessario definir as seguintes permissoes para a funcao alem dos que ja vem:
   
    # {
    #     "Effect": "Allow",
    #     "Action": [
    #         "s3:ListBucket",
    #         "s3:GetObject",
    #         "s3:PutObject"
    #     ],
    #     "Resource": INFORMAR
    # }

#Obs.: no campo "INFORMAR", pode-se adicionar um "*" para que valha para qualquer recurso

import boto3
import botocore
import csv
from datetime import timedelta

def ler_arquivo_s3(bucket, caminho_arquivo):
    s3 = boto3.client('s3')
    try:
        resposta = s3.get_object(Bucket=bucket, Key=caminho_arquivo)
        conteudo = resposta['Body'].read().decode('utf-8').strip()
        return conteudo
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao acessar o arquivo {caminho_arquivo}: {e}')
        return None

# converte uma string de tempo no formato 'HH:MM:SS' para um objeto timedelta
def parse_tempo(tempo_str):
    partes = tempo_str.split(':')
    horas = int(partes[0])
    minutos = int(partes[1])
    segundos = float(partes[2])
    return timedelta(hours=horas, minutes=minutos, seconds=segundos)

# lista os arquivos de um bucket S3 com base em um prefixo e sufixo especificos
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

def calcular_media_pico_memoria(bucket, prefixo, sufixo):
    arquivos = listar_arquivos(bucket, prefixo, sufixo)
    picos_memoria = []
    for arquivo in arquivos:
        conteudo = ler_arquivo_s3(bucket, arquivo)
        if conteudo:
            leitor = csv.DictReader(conteudo.splitlines(), delimiter=';')
            max_valor = None
            for linha in leitor:
                valor_memoria = float(linha['pss'])
                if max_valor is None or valor_memoria > max_valor:
                    max_valor = valor_memoria
            if max_valor is not None:
                picos_memoria.append(max_valor)
    if picos_memoria:
        media_picos = sum(picos_memoria) / len(picos_memoria)
        return media_picos
    else:
        return None

# formata um timedelta em string 'HH:MM:SS'
def formatar_timedelta(td):
    total_segundos = td.total_seconds()
    horas = int(total_segundos // 3600)
    minutos = int((total_segundos % 3600) // 60)
    segundos = total_segundos % 60
    return f"{horas:02}:{minutos:02}:{segundos:05.2f}"

def processar_arquivos_s3(bucket, prefixo):
    resultados = {}
    for input_set in range(100, 501, 100):
        for thread in [1, 2, 4, 8]:
            tempos = []
            sufixo_memoria = f'memory-{input_set}K-t{thread}.csv'

            for rodada in range(1, 4):
                sufixo_tempo = f'r{rodada}-{input_set}K-t{thread}.txt'
                
                arquivos_tempo = listar_arquivos(bucket, prefixo, sufixo_tempo)
                for caminho_arquivo in arquivos_tempo:
                    conteudo = ler_arquivo_s3(bucket, caminho_arquivo)
                    if conteudo is not None:
                        tempos.append(parse_tempo(conteudo))
                
            media_pico_memoria = calcular_media_pico_memoria(bucket, prefixo, sufixo_memoria) / 2**20
                
            if tempos and media_pico_memoria is not None:
                media_tempo = sum(tempos, timedelta())/len(tempos)
                resultados[f'{input_set}K-{thread}threads'] = (formatar_timedelta(media_tempo), media_tempo.total_seconds(), media_pico_memoria)
    
    print("aqui os resultados")
    print(resultados)

    return resultados


#utiliza precos datados de 28/08/2024 para a regiao us-east-1 para estimar o custo de ecs no amazon ec2 e ecs no aws fargate
def salvar_resultados_em_arquivo(resultados, nome_arquivo, ambiente):
    with open(nome_arquivo, 'w') as file:
        if ambiente == "EC2":
            #preco para uma instancia do tipo c7g.4xlarge 
            preco_por_hora = 0.58
            for chave, (valor_formatado, valor_segundos, pico_memoria) in resultados.items():
                if valor_segundos < 60:
                    valor_segundos = 60
                custo = (preco_por_hora / 3600) * valor_segundos
                file.write(f'{chave}:: Tempo: {valor_formatado}, Custo estimado: ${custo:.5f} USD, Pico memória: {pico_memoria:.2f} MB\n')
        else:
            v_cpu = 8
            memoria = 16
            preco_v_cpu_por_hora = 0.03238 
            preco_memoria_por_hora = 0.00356 
            for chave, (valor_formatado, valor_segundos, pico_memoria) in resultados.items():
                if valor_segundos < 60:
                    valor_segundos = 60
                custo_v_cpu = (preco_v_cpu_por_hora / 3600) * v_cpu * valor_segundos
                custo_memoria = (preco_memoria_por_hora / 3600) * memoria * valor_segundos
                custo_total = custo_v_cpu + custo_memoria
                file.write(f'{chave}:: Tempo: {valor_formatado}, Custo estimado: ${custo_total:.5f} USD, Pico memória: {pico_memoria:.2f} MB\n')

def enviar_arquivo_s3(bucket, caminho_arquivo, nome_arquivo_local):
    s3 = boto3.client('s3')
    try:
        s3.upload_file(nome_arquivo_local, bucket, caminho_arquivo)
        print(f'Arquivo {nome_arquivo_local} enviado para {caminho_arquivo} no bucket {bucket}.')
    except botocore.exceptions.ClientError as e:
        print(f'Erro ao enviar o arquivo {nome_arquivo_local} para {caminho_arquivo}: {e}')

def lambda_handler(event, context):
    ambiente = event.get('ambiente')
    bucket = 'INFORMAR'
    subpasta_dados="dados-containers"
    prefixo = f'{subpasta_dados}/{ambiente}/'
    
    resultados = processar_arquivos_s3(bucket, prefixo)
    
    nome_arquivo_local = f'/tmp/MEDIAS_EXECUCAO_{ambiente}.txt'
    caminho_arquivo_s3 = f'{subpasta_dados}/{ambiente}/MEDIAS_EXECUCAO_{ambiente}.txt'
    
    salvar_resultados_em_arquivo(resultados, nome_arquivo_local, ambiente)
    enviar_arquivo_s3(bucket, caminho_arquivo_s3, nome_arquivo_local)