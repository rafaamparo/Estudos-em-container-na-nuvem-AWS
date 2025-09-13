#!/bin/bash
if [ $# -lt 2 ]; then
  echo "entrada: $0 <imagem-px00> <chave 0..2>"
  exit 1
fi

IMAGE=$1
KEY=$2
OUTFILE="saida_${IMAGE}_chave${KEY}.txt"
IDS=()
CONTAINER_NAMES=()

START=$(date +%s%N)

case $KEY in
  0)
    ID1=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID1 $IMAGE 0 1 16)
    IDS+=($ID1)
    CONTAINER_NAMES+=(contID1)
    ;;
  1)
    ID1=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID3 $IMAGE 0 2 8)
    ID2=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID4 $IMAGE 1 2 8)
    IDS+=($ID1 $ID2)
    CONTAINER_NAMES+=(contID3 contID4)
    ;;
  2)
    ID1=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID5 $IMAGE 0 4 4)
    ID2=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID6 $IMAGE 1 4 4)
    ID3=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID7 $IMAGE 2 4 4)
    ID4=$(sudo docker run -d -v $HOME/.aws:/root/.aws --name contID8 $IMAGE 3 4 4)
    IDS+=($ID1 $ID2 $ID3 $ID4)
    CONTAINER_NAMES+=(contID5 contID6 contID7 contID8)
    ;;
  *)
    echo "chave inválida! Use 0, 1 ou 2."
    exit 1
    ;;
esac

# roda esperando todos os containers finalizarem, faz cleanup e calcula tempo
(
  sudo docker wait "${IDS[@]}" > /dev/null
  
  # Cleanup dos containers
  sudo docker rm "${CONTAINER_NAMES[@]}" > /dev/null 2>&1
  
  END=$(date +%s%N)
  DIFF=$((END - START))
  SEC=$((DIFF / 1000000000))
  MSEC=$(((DIFF / 1000000) % 1000))
  echo "Tempo total (incluindo cleanup): ${SEC}.${MSEC}s" > "$OUTFILE"
) & disown
