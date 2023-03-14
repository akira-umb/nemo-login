# To use this for local development:
# First build the image:
#
#   $ docker build -t portal-api:latest .
#

FROM ubuntu:20.04

MAINTAINER IGS IFX <igs-ifx@som.umaryland.edu>

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 libapache2-mod-wsgi-py3 \
    python3 python3-pip python3-setuptools python3-dev build-essential \
    python3-flask python3-requests python3-mysql.connector python3-boto3 python3-yaml \ 
    python3-zmq rustc curl screen

# curl --tlsv1 -vk https://bootstrap.pypa.io/get-pip.py -o get-pip.py
RUN mkdir /export 

WORKDIR /export/portal-api

# configure for dev vs prod ask about that later
# to remove unnecessary packages for testing
RUN pip3 install -Iv Flask-Caching==1.9.0 \
    && pip3 install -Iv neo4j==4.3.4 \
    && pip3 install -Iv Authlib==1.2.0 \
    && pip3 install -Iv SQLAlchemy==2.0.3 \
    && pip3 install -Iv Flask-SQLAlchemy==3.0.3 \
    && pip3 install -Iv Flask-Login==0.6.2 \
    && pip3 install -I pytest \
    && pip3 install -I coverage 
    
# CMD ["python", "app.py"]
COPY ./portal-apache2.conf /etc/apache2/sites-available/portal-apache2.conf

RUN a2enmod headers
RUN a2enmod proxy
RUN a2enmod proxy_http

RUN a2dissite 000-default.conf
RUN a2ensite portal-apache2.conf

EXPOSE 80

CMD /usr/sbin/apache2ctl -D FOREGROUND
