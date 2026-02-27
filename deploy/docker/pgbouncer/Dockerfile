FROM postgres:16-alpine

RUN apk add --no-cache pgbouncer bash

COPY deploy/docker/pgbouncer/start-pgbouncer.sh /usr/local/bin/start-pgbouncer.sh
RUN chmod +x /usr/local/bin/start-pgbouncer.sh

ENTRYPOINT ["/usr/local/bin/start-pgbouncer.sh"]
