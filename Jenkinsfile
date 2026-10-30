pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    environment {
        DATASENTINEL_DECISION = 'UNSET'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -eu
                            python3 --version
                            python3 -m pip install -r requirements.txt
                            python3 -m pip install pytest
                        '''
                    } else {
                        bat '''
                            @echo off
                            python --version
                            python -m pip install -r requirements.txt
                            if errorlevel 1 exit /b 1
                            python -m pip install pytest
                            if errorlevel 1 exit /b 1
                        '''
                    }
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python3 -m pytest -v'
                    } else {
                        bat 'python -m pytest -v'
                    }
                }
            }
        }

        stage('Analyze Datasets') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python3 scripts/run_pipeline.py'
                    } else {
                        bat 'python scripts\\run_pipeline.py'
                    }
                }
            }
        }

        
        stage('Read Protection Decision') {
            steps {
                script {
                    def decisionFile = 'reports/jenkins_decision.txt'

                    if (!fileExists(decisionFile)) {
                        error(
                            'Protection decision file was not generated. ' +
                            'Failing closed.'
                        )
                    }

                    // Read the file into a local variable first.
                    def decisionText = readFile(
                        file: decisionFile,
                        encoding: 'UTF-8'
                    ).trim()

                    echo "Raw protection decision from file: '${decisionText}'"

                    def validatedDecision = decisionText.toUpperCase()

                    if (!(validatedDecision in [
                        'ALLOW',
                        'REVIEW_REQUIRED',
                        'BLOCK'
                    ])) {
                        error(
                            'Invalid protection decision: ' +
                            validatedDecision +
                            '. Failing closed.'
                        )
                    }

                    // Update the environment only after validation.
                    env.DATASENTINEL_DECISION = validatedDecision

                    echo(
                        'DataSentinel protection decision: ' +
                        env.DATASENTINEL_DECISION
                    )
                }
            }
        }


        stage('Simulated Downstream Processing') {
            when {
                expression {
                    env.DATASENTINEL_DECISION == 'ALLOW'
                }
            }

            steps {
                echo 'Protection gate returned ALLOW.'
                echo 'Simulated downstream processing can proceed.'
                echo 'No external production system is connected by this demonstration.'
            }
        }

        stage('Enforce Protection Policy') {
            steps {
                script {
                    if (env.DATASENTINEL_DECISION == 'BLOCK') {
                        error(
                            'DataSentinel returned BLOCK. ' +
                            'Downstream processing is prohibited.'
                        )
                    }

                    if (env.DATASENTINEL_DECISION == 'REVIEW_REQUIRED') {
                        error(
                            'DataSentinel returned REVIEW_REQUIRED. ' +
                            'Human approval is required before processing.'
                        )
                    }

                    echo(
                        'Protection policy passed. ' +
                        'Downstream processing was permitted.'
                    )
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: 'reports/jenkins_analysis_*.json,reports/jenkins_decision.txt',
                allowEmptyArchive: true,
                fingerprint: true
            )
        }

        success {
            echo 'DataSentinel pipeline completed successfully.'
        }

        failure {
            echo(
                'DataSentinel pipeline failed or the protection policy ' +
                'prevented processing.'
            )
        }
    }
}
