# See https://stackoverflow.com/questions/72465421/how-to-use-poetry-with-docker
FROM python:3.12.4-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    BOOST_MAJOR=1 \
    BOOST_MINOR=86 \
    BOOST_PATCH=0 \
    GMP_VERSION=6.3.0 \
    METIS_VERSION=5.1.1 \
    LAPACK_VERSION=3.12.0 \
    MUMPS_VERSION=5.7.3.1 \
    IPOPT_VERSION=3.14.16 \
    CRITERION_VERSION=2.4.2 \
    PAPILO_REVISION=v2.2.0 \
    SOPLEX_REVISION=release-700 \
    WORKSPACE=/builds \
    INSTALLS=/installs \
    SCIP_TAG=v910 \
    SCIP_VERSION=9.1.0 \
    OPENMPI_VERSION=5.0.5 \
    HIGHS_VERSION=1.7.2 \
    SPRAL_VERSION=2024.05.08 \
    TBB_VERSION=2021.13.0

RUN apt-get update && apt-get install -y \
    wget \
    cmake \
    g++ \
    m4 \
    xz-utils \
    unzip \
    zlib1g-dev \
    libtbb-dev \
    libreadline-dev \
    pkg-config \
    git \
    flex \
    bison \
    libcliquer-dev \
    gfortran \
    libopenblas-dev \
    file \
    dpkg-dev \
    rpm

#### Installed below
# libopenmpi-dev \
# libboost1.81-dev \
# libgmp-dev \
# libtbb-dev \
# libmetis-dev \
# metis \
# libcriterion-dev


RUN mkdir $WORKSPACE && mkdir $INSTALLS
WORKDIR $WORKSPACE

RUN cd $WORKSPACE && \
    wget https://scipopt.org/download/external/hmetis-2.0pre1.tar.gz && \
    tar xfz hmetis-2.0pre1.tar.gz && \
    mkdir -p ${INSTALLS}/bin && \
    mv ${WORKSPACE}/hmetis-2.0pre1/Linux-x86_64/hmetis2.0pre1 ${INSTALLS}/bin/hmetis

# temporarily apt
RUN apt-get install -y libopenmpi-dev
# RUN cd ${WORKSPACE} && \
#     wget https://download.open-mpi.org/release/open-mpi/v5.0/openmpi-${OPENMPI_VERSION}.tar.gz && \
#     tar xzf openmpi-${OPENMPI_VERSION}.tar.gz && \
#     cd openmpi-${OPENMPI_VERSION} && \
#     ./configure --prefix=${INSTALLS} --enable-static --disable-shared && \
#     make install -j3

# temporarily apt (should be from openblas)
# RUN cd ${WORKSPACE} && \
#     wget https://github.com/Reference-LAPACK/lapack/archive/refs/tags/v$LAPACK_VERSION.tar.gz && \
#     tar xfz v$LAPACK_VERSION.tar.gz && \
#     cd ${WORKSPACE}/lapack-$LAPACK_VERSION && \
#     mkdir -p build && \
#     cd ${WORKSPACE}/lapack-$LAPACK_VERSION/build && \
#     cmake .. -DCMAKE_INSTALL_PREFIX=${INSTALLS} -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON && \
#     cmake --build . -j3 --target install

# temporarily apt
RUN apt-get install -y libboost1.81-dev
# RUN cd ${WORKSPACE} && \
#     echo "Download boost from https://boostorg.jfrog.io/artifactory/main/release/${BOOST_MAJOR}.${BOOST_MINOR}.${BOOST_PATCH}/source/boost_${BOOST_MAJOR}_${BOOST_MINOR}_${BOOST_PATCH}.tar.gz" && \
#     wget https://boostorg.jfrog.io/artifactory/main/release/${BOOST_MAJOR}.${BOOST_MINOR}.${BOOST_PATCH}/source/boost_${BOOST_MAJOR}_${BOOST_MINOR}_${BOOST_PATCH}.tar.gz && \
#     tar xfz boost_${BOOST_MAJOR}_${BOOST_MINOR}_${BOOST_PATCH}.tar.gz && \
#     cd ${WORKSPACE}/boost_${BOOST_MAJOR}_${BOOST_MINOR}_${BOOST_PATCH} && \
#     LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${INSTALLS}/lib/ ./bootstrap.sh --prefix=${INSTALLS} --with-libraries=program_options,serialization,regex,iostreams && \
#     ./b2 install 

# temporarily apt
RUN apt-get install -y libcriterion-dev
# RUN cd ${WORKSPACE} && \
#     wget https://github.com/Snaipe/Criterion/releases/download/v$CRITERION_VERSION/criterion-$CRITERION_VERSION-linux-x86_64.tar.xz && \
#     tar xf criterion-$CRITERION_VERSION-linux-x86_64.tar.xz && \
#     cp -r criterion-$CRITERION_VERSION/* ${INSTALLS}

# temporarily apt
RUN apt-get install -y libgmp-dev 
# RUN cd ${WORKSPACE} && \
#     wget https://gmplib.org/download/gmp/gmp-$GMP_VERSION.tar.xz && \
#     tar xf gmp-$GMP_VERSION.tar.xz && \
#     cd ${WORKSPACE}/gmp-$GMP_VERSION && \
#     ./configure --with-pic --enable-cxx --disable-shared --prefix=${INSTALLS} && \
#     make install -j3 

# temporarily apt
RUN apt-get install -y libtbb-dev
# RUN cd ${WORKSPACE} && \
#     wget https://github.com/oneapi-src/oneTBB/archive/refs/tags/v$TBB_VERSION.tar.gz && \
#     tar xvf v$TBB_VERSION.tar.gz && \
#     mkdir ${WORKSPACE}/oneTBB-$TBB_VERSION/build && \
#     cd ${WORKSPACE}/oneTBB-$TBB_VERSION/build && \
# RUN cd ${WORKSPACE} && \
#     git clone https://github.com/oneapi-src/oneTBB.git && cd oneTBB && mkdir build && cd build && \
#     cmake .. -DCMAKE_INSTALL_PREFIX=${INSTALLS} -DCMAKE_BUILD_TYPE=Release -DTBB_TEST=OFF -DTBB_EXAMPLES=OFF -DTBB4PY_BUILD=OFF -DBUILD_SHARED_LIBS=ON && \
#     make -j3 && make install

# temporarily apt
RUN apt-get install -y libmetis-dev metis
# RUN cd ${WORKSPACE} && \
#     wget https://github.com/KarypisLab/GKlib/archive/refs/tags/METIS-v$METIS_VERSION-DistDGL-0.5.tar.gz && \
#     tar xfz METIS-v$METIS_VERSION-DistDGL-0.5.tar.gz && \
#     cd ${WORKSPACE}/GKlib-METIS-v$METIS_VERSION-DistDGL-0.5 && \
#     make config prefix=${WORKSPACE}/GKlib-METIS-v$METIS_VERSION-DistDGL-0.5 && \
#     make -j && \
#     make install && \
#     cd ${WORKSPACE} && \
#     wget https://github.com/KarypisLab/METIS/archive/refs/tags/v$METIS_VERSION-DistDGL-v0.5.tar.gz && \
#     tar xfz v$METIS_VERSION-DistDGL-v0.5.tar.gz && \
#     cd ${WORKSPACE}/METIS-$METIS_VERSION-DistDGL-v0.5 && \
#     make config prefix=${INSTALLS} gklib_path=${WORKSPACE}/GKlib-METIS-v$METIS_VERSION-DistDGL-0.5 && \
#     make && \
#     make install -j3

RUN cd ${WORKSPACE} && \
    wget https://github.com/ERGO-Code/HiGHS/archive/refs/tags/v${HIGHS_VERSION}.tar.gz && \
    tar xzf v${HIGHS_VERSION}.tar.gz && \
    cd ${WORKSPACE}/HiGHS-${HIGHS_VERSION} && \
    LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${INSTALLS}/lib/ cmake -S . -B build -DCMAKE_INSTALL_PREFIX=${INSTALLS} -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF && \
    cmake --build build -j 3 && \
    cd build && ctest && cd .. && \
    cmake --install build 

# depends on METIS
ENV MUMPS_VERSION=3.0.7 
RUN cd ${WORKSPACE} && \
    wget https://github.com/coin-or-tools/ThirdParty-Mumps/archive/refs/tags/releases/$MUMPS_VERSION.zip && \
    unzip $MUMPS_VERSION.zip && \
    cd ${WORKSPACE}/ThirdParty-Mumps-releases-$MUMPS_VERSION && \
    ./get.Mumps && \
    PATH=$PATH:${INSTALLS}/bin/ LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${INSTALLS}/lib/ ./configure --prefix=${INSTALLS} --disable-shared --enable-static --with-lapack-lflags="-llapack -lblas -lgfortran -lquadmath -lm" && \
    make -j3 && \
    make install 
# ENV MUMPS_VERSION=5.7.3.1 
# RUN cd ${WORKSPACE} && \
#     wget https://github.com/scivision/mumps/archive/refs/tags/v${MUMPS_VERSION}.tar.gz && \
#     tar xfz v${MUMPS_VERSION}.tar.gz && \
#     cd ${WORKSPACE}/mumps-${MUMPS_VERSION} && \
#     LIBRARY_PATH=$LIBRARY_PATH:${INSTALLS}/lib/ cmake -B build -DCMAKE_INSTALL_PREFIX=${INSTALLS} -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -Dmetis=no -Dopenmp=false && \
#     cmake --build build -j 3 && \
#     cmake --install build 

# depends on metis, uses openblas and lapack from repos
# RUN apt-get install -y ninja-build && \
#     pip3 install meson && \
#     cd ${WORKSPACE} && \
#     wget https://github.com/ralna/spral/archive/refs/tags/v${SPRAL_VERSION}.tar.gz && \
#     tar xfz v${SPRAL_VERSION}.tar.gz && \
#     cd ${WORKSPACE}/spral-${SPRAL_VERSION} && \
#     meson setup builddir \
#     --prefix=${INSTALLS}  \
#     -Dexamples=true -Dtests=true \
#     -Dlibblas=openblas \
#     -Dliblapack=lapack \
#     -Dlibmetis=metis \
#     -Dlibmetis_path=${INSTALLS}/lib/ && \
#     meson compile -C builddir -j 6 && \
#     meson install -C builddir

RUN cd ${WORKSPACE} && \
    wget https://github.com/coin-or/Ipopt/archive/releases/$IPOPT_VERSION.zip && \
    unzip $IPOPT_VERSION.zip && \
    cd ${WORKSPACE}/Ipopt-releases-$IPOPT_VERSION && \
    CPATH=${INSTALLS}/include/ LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${INSTALLS}/lib/ ./configure --prefix=${INSTALLS} --enable-static --disable-shared \
    --with-lapack-lflags="-L${INSTALLS}/lib/ -llapack -lblas -lgfortran -lquadmath -lm" && \
    make -j6 && make test && make install 
# --with-mumps-lflags="-L${INSTALLS}/lib/ -ldmumps -lmumps_common -lsmumps -lm" \
# --with-mumps-cflags="-I${INSTALLS}/include/" && \
# make -j6 && make install 


# included in scipoptsuite
# RUN cd ${WORKSPACE} && \
#     git clone https://github.com/scipopt/soplex.git && \
#     cd ${WORKSPACE}/soplex && \
#     git checkout $SOPLEX_REVISION && \
#     mkdir ${WORKSPACE}/soplex/build && \
#     cd ${WORKSPACE}/soplex/build && \
#     LD_LIBRARY_PATH=$LD_LIBRARY_PATH:${INSTALLS}/lib/ cmake .. -DCMAKE_INSTALL_PREFIX=${INSTALLS} -DCMAKE_BUILD_TYPE=Release && \
#     make -j && \
#     make install


RUN cd ${WORKSPACE} && \
    wget https://github.com/scipopt/scip/releases/download/${SCIP_TAG}/scipoptsuite-${SCIP_VERSION}.tgz && \
    tar xfz scipoptsuite-${SCIP_VERSION}.tgz && \
    cd ${WORKSPACE}/scipoptsuite-${SCIP_VERSION} && \
    mkdir build && \
    cd ${WORKSPACE}/scipoptsuite-${SCIP_VERSION}/build && \
    PATH=$PATH:${INSTALLS}/bin/ cmake .. \
    -DCMAKE_INSTALL_PREFIX=${INSTALLS} \
    -DCMAKE_BUILD_TYPE=Release \
    -DLPS=spx \
    -DSYM=snauty \
    -DBoost_USE_STATIC_LIBS=on \
    -DPAPILO=true \
    -DLAPACK=true \
    -DZIMPL=true \
    -DGMP=true \
    -DREADLINE=true \
    -DIPOPT=true \
    -DIPOPT_DIR=${INSTALLS} \
    -DCMAKE_C_FLAGS="-s -I${INSTALLS}/include/ -I${INSTALLS}/include/highs -L${INSTALLS}/lib/" \
    -DCMAKE_CXX_FLAGS="-s -I${INSTALLS}/include/ -I${INSTALLS}/include/highs -L${INSTALLS}/lib/" \
    -DTPI=tny && \
    make -j6 && \
    make install
RUN cd ${WORKSPACE}/scipoptsuite-${SCIP_VERSION}/build && \
    make test

# # to run poetry directly as soon as it's installed
ENV PATH="$POETRY_HOME/bin:$PATH"

# install poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# copy only pyproject.toml and poetry.lock file nothing else here
COPY poetry.lock pyproject.toml ./
# copy source code as own layer
COPY README.md ./
COPY src ./src

# this will create the folder /app/.venv and install the application
RUN poetry install --no-ansi --without dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:/installs/bin:$PATH"


# FROM python:3.12.2-slim-bookworm

# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1 \
#     PATH="/app/.venv/bin:/installs/bin:$PATH"

# WORKDIR /app
# # make a user so not running as root
# RUN adduser --system --no-create-home app

# # copy the venv folder from builder image 
# COPY --from=builder /app/.venv /app/.venv
# COPY --from=builder /app/src /app/src

# USER app
# ENTRYPOINT [ "/app/src/entrypoint.sh" ]

