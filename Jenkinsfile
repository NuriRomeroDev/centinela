pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Linter & Static Analysis') {
            steps {
                dir('backend') {
                    sh 'python3 -m venv .venv'
                    sh '.venv/bin/pip install -q -e ".[dev]"'
                    sh '.venv/bin/flake8'
                    sh '.venv/bin/black --check .'
                }
                dir('frontend') {
                    sh 'npm ci'
                    sh 'npm run lint'
                }
            }
        }

        stage('Unit Testing') {
            steps {
                dir('backend') {
                    sh '.venv/bin/pytest --cov --cov-fail-under=80'
                }
                dir('frontend') {
                    sh 'npm run test:coverage'
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker compose build'
            }
        }
    }
}
