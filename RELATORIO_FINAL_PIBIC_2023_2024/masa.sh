#!/bin/bash
export OMP_NUM_THREADS=$1

arquivos=($(ls ./sequencias/*.fasta))
quant_arq=${#arquivos[@]}

#guarda dados de cada alinhamento linha a linha
function escreve_csv() {
    dia=$(date +"%d/%m/%Y")
    hora=$(date +"%H:%M:%S")
    arq1=$(basename "${arquivos[$1]}")
    tam1=$(head -1 resul/alignment.00.txt | awk -F[=\(\)] '{print '' $2}')
    arq2=$(basename "${arquivos[$2]}")
    tam2=$(head -2 resul/alignment.00.txt | tail -1 | awk -F[=\(\)] '{print '' $2}')
    tempo=$(cat resul/tempo.txt)

    #analisando pico de memoria de cada alinhamento
    #a variavel tempo_formatado indica quanto tempo foi necessario para atingir o pico de memoria deste alinhamento desde o inicio de sua execucao 
    arquivo="memory_$5.csv"
    linha_pico_memoria=$(awk -F';' 'NR > 1 {print $10, $1}' "$arquivo" | sort -nk1 | tail -1)
    maior_pss=$(echo "$linha_pico_memoria" | awk '{print $1}')
    maior_pss_mb=$(echo "scale=2; $maior_pss / 1048576" | bc)
    timestamp_maior=$(echo "$linha_pico_memoria" | cut -d' ' -f2-)

    tempo_inicial_s=$(date -d "$4" +%s.%N)
    tempo_maior_s=$(date -d "$timestamp_maior" +%s.%N)
    diferenca_tempo=$(echo "scale=2; ($tempo_maior_s - $tempo_inicial_s)/1" | bc)

    segundos=$(echo $diferenca_tempo | cut -d'.' -f1)
    centesimos=$(echo $diferenca_tempo | cut -d'.' -f2)

    #formata a diferença em HH:MM:SS.CC
    tempo_formatado=$(date -u -d "@$segundos" '+%H:%M:%S')
    tempo_formatado="${tempo_formatado}.${centesimos}"

    linha="${dia}; ${hora}; ${arq1}; ${tam1}; ${arq2}; ${tam2}; ${maior_pss_mb}; ${tempo_formatado}; ${tempo};"
    echo "$linha" >> $3
}

#realiza alinhamentos par-a-par
#alinha cada i-esima sequencia com a j-esima sequencia do grupo de sequencias input set, em que j >= i
for((i=0; i<quant_arq; i++))
do
    for((j=i; j<quant_arq; j++))
    do
        mkdir resul
        touch resul/tempo.txt

        tempo_inicial=$(date +"%Y-%m-%d %H:%M:%S.%N")
        tempo_inicial_formatado=${tempo_inicial// /_}

        python3 ./rprof.py -m -g -t $tempo_inicial_formatado "/usr/bin/time -f "%E" -o resul/tempo.txt ./masa-openmp-1.0.1.1024/masa-openmp --verbose=0 --work-dir=resul ${arquivos[$i]} ${arquivos[$j]}"
        
        escreve_csv $i $j $2 "$tempo_inicial" "$tempo_inicial_formatado"

        rm memory_${tempo_inicial_formatado}.csv
        rm -rf resul
    done
done