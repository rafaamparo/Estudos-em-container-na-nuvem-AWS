FROM ubuntu:latest

WORKDIR /app

#para que o comando a seguir funcione, deve-se clonar a aplicacao MASA-openMP:
#para isso, execute no diretorio em que deseja trabalhar os seguintes comandos:

#1) git clone https://github.com/edanssandes/MASA-OpenMP.git
#2) mv MASA-OpenMP/masa-openmp-1.0.1.1024/ ./
#3) rm -rf MASA-OpenMP/

#caso esteja dificil entender, acesse o tutorial na secao "passo a passo para utilizar o ECS"
#https://docs.google.com/document/d/1BYJx32pcGeCqaitQW26pobPJ-2dd-LrGgrfkrmMjOvA/edit?usp=sharing

COPY masa-openmp-1.0.1.1024 /app/masa-openmp-1.0.1.1024

COPY masa.sh entrypoint.sh rprof.py rprof-plotter.py /app/

#instalacao de dependencias

RUN apt-get update && \
    apt-get install -y g++ make time python3 python3-pip curl jq bc && \
    pip3 install awscli psutil matplotlib --break-system-packages && \
    chmod +x ./masa.sh ./entrypoint.sh

WORKDIR /app/masa-openmp-1.0.1.1024

#realizando ajustes no codigo para gerar compatibilidade com a arquitetura ARM
#o processador utilizado foi o graviton3 presente na instancia c7g.4xlarge

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