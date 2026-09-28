# FROM postgis/postgis:15-3.3

# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#         postgresql-15-pgvector && \
#     rm -rf /var/lib/apt/lists/*
FROM pgvector/pgvector:pg15

RUN apt-get update && \
    apt-get install -y --no-install-recommends postgis postgresql-15-postgis-3 && \
    rm -rf /var/lib/apt/lists/*