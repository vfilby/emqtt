run: 
	python runner.py

test:
	python -m pytest -p no:warnings tests/

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d | xargs rm -fr

docker:
	docker build -t emqtt:development .

docker-test:
	docker build -t emqtt:development .
	docker run -it --rm emqtt:development python3 -m pytest -p no:warnings tests/
	docker rmi emqtt:development

	
