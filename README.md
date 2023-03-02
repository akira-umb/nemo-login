# Intro
- branch copied from trunk
- refactoring + porting login features from jwt_auth branch

# Goals
- no login: done lol
- first party:
- third party:
- configurable:

# Depdencies
- flask-login
- authlib

# Set Up

## neo4j
- create folder 'data'
- under 'data' create folders 'databases', 'transactions'
- get a backup from server
- move backup zip to 'databases' and unzip

## api
- copy over relevant config files, at the time of writing for Nemo
    - conf.py
    - config.ini
    - facets.yml
    - models_metadata.yml

## ui
- logo.svg and something else, but just static files
- wont affect app only appearance
- images
    - favicon.ico
    - logo.svg
- styles
    - skin_custom.less
- site_meta-information.json

# run

```
docker-compose up -d
```

```
docker-compose down -v
```

```
docker exec -it jwt_auth-neo4j-1 cat /var/log/neo4j/neo4j.log
```

tar -xvf jules-backup-2022-05-19.tar.gz -C .
ssh awatanabe@jade.igs.umaryland.edu
http://subversion.igs.umaryland.edu/svn/ENGR/portal/branches/jwt_auth
http://websvn.igs.umaryland.edu/wsvn/IGS/ENGR/portal/branches/jwt_auth
docker exec -it jwt_auth-neo4j-1 cat /var/log/neo4j/neo4j.log

## Testing
- for now try tests at same lvl as portal-api
- may need to embedd it though