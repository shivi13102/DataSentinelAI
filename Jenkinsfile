pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    parameters {
        choice(
            name: 'SCENARIO',
            choices: ['current', 'healthy', 'suspicious', 'critical'],
            description: 'Dataset pair used for the deterministic protection run.'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare Build Artifacts') {
            steps {
                script {
                    def artifactDirectory =
                        "reports/jenkins/${env.BUILD_NUMBER}"
                    dir(artifactDirectory) {
                        // Remove artifacts from a replay of this build so a
                        // stale ALLOW cannot survive an earlier attempt.
                        deleteDir()
                    }
                }
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
                    if (!(params.SCENARIO in [
                        'current',
                        'healthy',
                        'suspicious',
                        'critical'
                    ])) {
                        error('Unknown DataSentinel scenario.')
                    }

                    def baseline = 'data/raw/baseline.csv'
                    def current = 'data/raw/current.csv'
                    if (params.SCENARIO != 'current') {
                        baseline = "tests/fixtures/protection/${params.SCENARIO}_baseline.csv"
                        current = "tests/fixtures/protection/${params.SCENARIO}_current.csv"
                    }

                    def artifactDirectory =
                        "reports/jenkins/${env.BUILD_NUMBER}"

                    if (isUnix()) {
                        sh """
                            set -eu
                            python3 scripts/run_pipeline.py \\
                              --baseline '${baseline}' \\
                              --current '${current}' \\
                              --artifact-dir '${artifactDirectory}' \\
                              --run-id '${env.BUILD_NUMBER}'
                        """
                    } else {
                        bat """
                            @echo off
                            python scripts\\run_pipeline.py --baseline "${baseline}" --current "${current}" --artifact-dir "${artifactDirectory}" --run-id "${env.BUILD_NUMBER}"
                            if errorlevel 1 exit /b 1
                        """
                    }
                }
            }
        }

        stage('Read Protection Decision') {
            steps {
                script {
                    def decisionFile =
                        "reports/jenkins/${env.BUILD_NUMBER}/jenkins_decision.txt"

                    if (!fileExists(decisionFile)) {
                        error(
                            'The current build did not generate a protection '
                            + 'decision artifact. Failing closed.'
                        )
                    }

                    def decision = readFile(
                        file: decisionFile,
                        encoding: 'UTF-8'
                    ).trim()

                    if (!(decision in [
                        'ALLOW',
                        'REVIEW_REQUIRED',
                        'BLOCK'
                    ])) {
                        error(
                            "Invalid protection decision '${decision}'. "
                            + 'Failing closed.'
                        )
                    }

                    currentBuild.description =
                        "DataSentinel protection: ${decision}"
                    echo "Current build protection decision: ${decision}"
                }
            }
        }

        stage('Simulated Downstream Processing') {
            when {
                expression {
                    def decisionFile =
                        "reports/jenkins/${env.BUILD_NUMBER}/jenkins_decision.txt"
                    fileExists(decisionFile) &&
                        readFile(
                            file: decisionFile,
                            encoding: 'UTF-8'
                        ).trim() == 'ALLOW'
                }
            }
            steps {
                script {
                    // Re-read at the execution boundary; the decision file,
                    // not an AI response or a prior environment value, is authoritative.
                    def decisionFile =
                        "reports/jenkins/${env.BUILD_NUMBER}/jenkins_decision.txt"
                    if (!fileExists(decisionFile)) {
                        error('Protection decision disappeared; failing closed.')
                    }
                    def decision = readFile(
                        file: decisionFile,
                        encoding: 'UTF-8'
                    ).trim()
                    if (decision != 'ALLOW') {
                        error(
                            'Downstream execution requires an exact ALLOW '
                            + 'decision from this build.'
                        )
                    }

                    echo 'Protection gate returned ALLOW.'
                    echo 'Simulated downstream processing can proceed.'
                    echo(
                        'No external production system is connected by '
                        + 'this demonstration.'
                    )
                }
            }
        }

        stage('Enforce Protection Policy') {
            steps {
                script {
                    def decisionFile =
                        "reports/jenkins/${env.BUILD_NUMBER}/jenkins_decision.txt"
                    if (!fileExists(decisionFile)) {
                        error('Protection decision is missing; failing closed.')
                    }
                    def decision = readFile(
                        file: decisionFile,
                        encoding: 'UTF-8'
                    ).trim()

                    if (!(decision in [
                        'ALLOW',
                        'REVIEW_REQUIRED',
                        'BLOCK'
                    ])) {
                        error(
                            "Invalid protection decision '${decision}'. "
                            + 'Failing closed.'
                        )
                    }

                    if (decision == 'BLOCK') {
                        currentBuild.result = 'UNSTABLE'
                        echo(
                            'BLOCK: downstream processing was prohibited. '
                            + 'This is a protection outcome, not an analysis '
                            + 'failure.'
                        )
                    } else if (decision == 'REVIEW_REQUIRED') {
                        currentBuild.result = 'UNSTABLE'
                        echo(
                            'REVIEW_REQUIRED: downstream processing remains '
                            + 'prohibited because no approval workflow exists.'
                        )
                    } else {
                        echo 'ALLOW: protection policy permits processing.'
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: "reports/jenkins/${env.BUILD_NUMBER}/**",
                allowEmptyArchive: true,
                fingerprint: true
            )
        }

        success {
            echo 'DataSentinel pipeline completed successfully.'
        }

        unstable {
            echo(
                'DataSentinel analysis completed, but the protection policy '
                + 'prohibited automatic downstream processing.'
            )
        }

        failure {
            echo(
                'DataSentinel pipeline failed before a trustworthy '
                + 'protection outcome could be enforced.'
            )
        }
    }
}
