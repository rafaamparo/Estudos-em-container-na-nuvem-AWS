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

    linha="${RODADA};$4;${dia};${hora};${arq1};${tam1};${arq2};${tam2};${tempo}"
    echo "$linha" >> $3
}

# quantidade de alinhamentos calculada como combinacao de n 2 a 2 (quantidade de pares possivesi detre as n sequencias) 
quant_alinhamentos=$((quant_arq * (quant_arq - 1) / 2))

# $3: numero de containers
# $4: id do container atual
inicio=$((quant_alinhamentos / $3 * $4))
fim=$((quant_alinhamentos / $3 * ($4 + 1)))

cont_alinhamentos=0

for((i=0; i<quant_arq; i++))
do
    for((j=i+1; j<quant_arq; j++))
    do
        if((cont_alinhamentos >= inicio && cont_alinhamentos < fim)); then
            mkdir resul
            touch resul/tempo.txt

            /usr/bin/time -f "%E" -o resul/tempo.txt ./masa-openmp-1.0.1.1024/masa-openmp --verbose=0 --work-dir=resul ${arquivos[$i]} ${arquivos[$j]}
            
            escreve_csv $i $j $2 $4

            rm -rf resul
        fi

        cont_alinhamentos=$((cont_alinhamentos + 1))
    done
done