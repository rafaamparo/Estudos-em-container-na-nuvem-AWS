import csv

def analisar_linha(linha):
    print(f"Analisando linha: {linha}")  

    partes = linha.split(':: Tempo: ')
    config = partes[0].strip()
    tempo_execucao_str, _ = partes[1].split(', Custo estimado: ')

    config = config.split('-')
    tamanho_input = config[0]
    num_threads = int(config[1].replace('threads', ''))

    tempo_partes = tempo_execucao_str.split(':')
    horas = int(tempo_partes[0])
    minutos = int(tempo_partes[1])
    segundos = float(tempo_partes[2])

    tempo_total_segundos = horas * 3600 + minutos * 60 + segundos

    return tamanho_input, num_threads, tempo_total_segundos


def calcular_speedup_eficiencia(dados):
    resultados = {}
    for tamanho in ['100K', '200K', '300K', '400K', '500K']:
        for threads in [1, 2, 4, 8]:
            chave = f"{tamanho}-{threads}threads"
            if chave in dados:
                tempo = dados[chave]['tempo']
                if threads == 1:
                    tempo_base = tempo
                    continue

                speedup = tempo_base / tempo
                eficiencia = speedup / threads
                resultados[chave] = {
                    'speedup': speedup,
                    'eficiencia': eficiencia
                }

    return resultados

def main(arquivo_entrada, arquivo_saida):
    dados = {}
    with open(arquivo_entrada, 'r', encoding='utf-8') as arq:
        for linha in arq:
            resul = analisar_linha(linha)
            if resul:
                tamanho, threads, tempo_total = resul
                chave = f"{tamanho}-{threads}threads"
                dados[chave] = {
                    'tempo': tempo_total
                }
    
    resultados = calcular_speedup_eficiencia(dados)
    
    with open(arquivo_saida, 'w', newline='') as arq:
        writer = csv.writer(arq)
        writer.writerow(["Configuraçao", "Speed-up", "Eficiencia"])
        for chave in resultados:
            speedup = resultados[chave]['speedup']
            eficiencia = resultados[chave]['eficiencia']
            writer.writerow([chave, f"{speedup:.2f}", f"{eficiencia:.2f}"])
    
    print(f"Resultados gravados em {arquivo_saida}")

ambiente = 'EC2'
arquivo_entrada = f'MEDIAS_EXECUCAO_{ambiente}.txt'
arquivo_saida = f'resultado_{ambiente}.csv'
main(arquivo_entrada, arquivo_saida)
