SERVICE_TAG:=ghcr.io/shrimpsizemoose/demo-trekker:1.0

build:
	docker build . --tag ${SERVICE_TAG}

run:
	docker run --rm \
		-e STUDENT_ID=igor.mosyagin \
		-e TOKEN=sk-ptokenitokenztonenda \
		-e DEMO_PARAMETER=wow-such-secret-much-param \
		${SERVICE_TAG}
