#!/bin/bash

export OMP_NUM_THREADS=$1

arquivos=($(ls ./sequencias/*.fasta))
quant_arq=${#arquivos[@]}

echo "Encontradas ${quant_arq} sequências para processamento"

#guarda dados de cada alinhamento linha a linha
function escreve_csv() {
    dia=$(date +"%d/%m/%Y")
    hora=$(date +"%H:%M:%S")
    arq1=$(basename "${arquivos[$1]}")
    tam1=$(head -1 resul/alignment.00.txt | awk -F[=\(\)] '{print $2}')
    arq2=$(basename "${arquivos[$2]}")
    tam2=$(head -2 resul/alignment.00.txt | tail -1 | awk -F[=\(\)] '{print $2}')
    tempo=$(cat resul/tempo.txt)

    linha="${RODADA};$4;${dia};${hora};${arq1};${tam1};${arq2};${tam2};${tempo}"
    echo "$linha" >> $3
    
    echo "Alinhamento concluído: ${arq1} vs ${arq2} - ${tempo} segundos"
}

# quantidade de alinhamentos calculada como combinacao de n 2 a 2 (quantidade de pares possíveis entre as n sequencias)
quant_alinhamentos=$((quant_arq * (quant_arq - 1) / 2))

echo "Total de alinhamentos possíveis: $quant_alinhamentos"

# Parâmetros de paralelização
# $2: arquivo CSV de saída
# $3: numero total de containers
# $4: id do container atual

arquivo_csv=$2
num_containers=${3:-1}
container_id=${4:-0}

echo "Configuração de paralelização:"
echo "  - Número de containers: $num_containers"
echo "  - ID deste container: $container_id"
echo "  - Threads OpenMP: $OMP_NUM_THREADS"

# Calculando faixa de alinhamentos para este container
inicio=$((quant_alinhamentos / num_containers * container_id))
fim=$((quant_alinhamentos / num_containers * (container_id + 1)))

# Ajustando para o último container pegar os alinhamentos restantes
if [ $container_id -eq $((num_containers - 1)) ]; then
    fim=$quant_alinhamentos
fi

echo "Este container processará alinhamentos de $inicio a $((fim-1))"

cont_alinhamentos=0

for((i=0; i<quant_arq-1; i++)); do
    for((j=i+1; j<quant_arq; j++)); do
        if [[ $cont_alinhamentos -ge $inicio && $cont_alinhamentos -lt $fim ]]; then
            echo "Processando alinhamento $((cont_alinhamentos + 1))/$quant_alinhamentos: ${arquivos[$i]} vs ${arquivos[$j]}"
            
            mkdir -p resul
            touch resul/tempo.txt

            # ALTERAÇÃO AQUI: %e em vez de %E para ter tempo em segundos
            /usr/bin/time -f "%e" -o resul/tempo.txt ./masa-openmp-1.0.1.1024/masa-openmp --verbose=0 --work-dir=resul ${arquivos[$i]} ${arquivos[$j]}

            if [ $? -eq 0 ]; then
                escreve_csv $i $j $arquivo_csv $container_id
            else
                echo "ERRO no alinhamento: ${arquivos[$i]} vs ${arquivos[$j]}"
            fi

            rm -rf resul
        fi
        cont_alinhamentos=$((cont_alinhamentos + 1))
    done
done

echo "Container $container_id finalizou seu processamento"
echo "Alinhamentos processados: $((fim - inicio))"
