pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
    }

    environment {
        IMAGE_NAME = 'aceest-fitness'
        IMAGE_TAG = "${BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build --tag ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }

        stage('Lint and syntax') {
            steps {
                sh 'docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} ruff check .'
                sh 'docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} python -m compileall -q app.py'
            }
        }

        stage('Unit tests') {
            steps {
                sh 'docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} pytest'
            }
        }
    }

    post {
        always {
            sh 'docker image rm --force ${IMAGE_NAME}:${IMAGE_TAG} || true'
            cleanWs()
        }
    }
}
