rm -r portal-ui/.tmp
rm -r portal-ui/dist
docker-compose down -v
docker-compose build
docker-compose up -d