FROM python:alpine3.7
COPY . /TN-ETH-Gateway
WORKDIR /TN-ETH-Gateway
RUN apk update
RUN apk upgrade
RUN apk add build-base 
RUN apk add postgresql-dev gcc python3-dev musl-dev
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 5000
CMD python ./start.py