FROM ubuntu:latest

WORKDIR /app

COPY masa-openmp-1.0.1.1024 /app/masa-openmp-1.0.1.1024

COPY masa.sh entrypoint.sh /app/

# instalando dependencias

RUN apt-get update && \
    apt-get install -y g++ make time python3 python3-pip curl jq && \
    pip3 install awscli --break-system-packages && \
    chmod +x ./masa.sh ./entrypoint.sh

WORKDIR /app/masa-openmp-1.0.1.1024

# configurando arquivos do masa para rodar no graviton

RUN sed -e 's/$PLATFORM //g' -i configure configure.ac ./libs/masa-core/configure ./libs/masa-core/configure.ac && \
    sed -e 's/$COMMONFLAGS -malign-double/$COMMONFLAGS/g' -i ./libs/masa-core/configure && \
    sed -e 's/$CFLAGS  -malign-double/$CFLAGS/g' -i ./libs/masa-core/configure && \
    sed -i '74,75d' ./libs/masa-core/configure.ac && \
    sed -e 's/masa_openmp_CXXFLAGS = -malign-double -fno-strict-aliasing/masa_openmp_CXXFLAGS = -fno-strict-aliasing/g' -i Makefile.am Makefile.in && \
    ./configure CC=gcc \
    CFLAGS='-march=armv8.2-a+fp16+rcpc+dotprod+crypto -mtune=neoverse-n1' \
    CXX="g++ -march=armv8.2-a+fp16+rcpc+dotprod+crypto -mtune=neoverse-n1" \
    CXXFLAGS='-march=armv8.2-a+fp16+rcpc+dotprod+crypto -mtune=neoverse-n1' && \
    make

WORKDIR /app

CMD ["./entrypoint.sh"]