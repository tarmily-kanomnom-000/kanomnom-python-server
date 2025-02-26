# kanomnom-python-server

## Production

make sure to fill out .env

It is expected that this will be ran in conjuction with kanomnom-server and medusa-store

docker compose -f docker-compose-prod.yaml down && docker compose -f docker-compose-prod.yaml build --no-cache && docker compose -f docker-compose-prod.yaml up -d

## Dev

docker compose -f docker-compose-dev.yaml down && docker compose -f docker-compose-dev.yaml build && docker compose -f docker-compose-dev.yaml up