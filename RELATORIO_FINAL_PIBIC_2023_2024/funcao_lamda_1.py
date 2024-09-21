import base64
import gzip
import boto3
import json

#funcao lambda executada ao final de uma tarefa (que a envia os dados contidos no payload)
#responsavel por lancar tarefas em sequencia ate que o experimento termine
#quando nao houver mais tarefas a serem lancadas, invoca a funcao_lamda_2 


#para executa-la, e necessario definir as seguintes permissoes para a funcao alem dos que ja vem:

    # {
    #     "Effect": "Allow",
    #     "Action": "ecs:DescribeTasks",
    #     "Resource": INFORMAR"
    # },
    # {
    #     "Effect": "Allow",
    #     "Action": "s3:PutObject",
    #     "Resource": INFORMAR
    # },
    # {
    #     "Effect": "Allow",
    #     "Action": "ecs:RunTask",
    #     "Resource": INFORMAR
    # },
    # {
    #     "Effect": "Allow",
    #     "Action": "iam:PassRole",
    #     "Resource": INFORMAR
    # },
    # {
    #     "Effect": "Allow",
    #     "Action": "lambda:InvokeFunction",
    #     "Resource": INFORMAR
    # }

#Obs.: no campo "INFORMAR", pode-se adicionar um "*" para que valha para qualquer recurso

def lambda_handler(event, context):
    #obtendo dados para coleta do tempo cobrado e para identificacao da pasta na qual esse dado sera guardado
    dados_decoded = base64.b64decode(event['awslogs']['data'])
    dados_descompactados = gzip.decompress(dados_decoded).decode('utf-8')
    payload = json.loads(dados_descompactados)['logEvents'][0]['message'][4:]
    
    print("payload", payload)
    
    #capturando as informacoes da mensagem capturada pela mensagem-gatilho do cloudwatch logs

    payload = json.loads(payload)
    task_arn = payload['task_arn']
    cluster = payload['cluster']
    ambiente = payload['ambiente']
    dia_inicial = payload['dia_inicial']
    hora_inicial = payload['hora_inicial']
    input_set = int(payload['input_set'])
    rodada = int(payload['rodada'])
    threads = int(payload['threads'])
    
    print("dados", task_arn, cluster, ambiente, dia_inicial, hora_inicial, input_set, rodada, threads)
    
    try:
        #consultando os tempos inicial e final de cobranca
        ecs = boto3.client('ecs')
        task_info = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])['tasks'][0]
        t_inicio = task_info.get('pullStartedAt', '')
        t_fim = task_info.get('executionStoppedAt', '')
        
        #esperando ate que os dados estejam disponiveis
        while not (t_inicio and t_fim):
            task_info = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])['tasks'][0]
            t_inicio = task_info.get('pullStartedAt', '')
            t_fim = task_info.get('executionStoppedAt', '')
    
        diferenca = t_fim - t_inicio
    
        #enviando esse tempo ao s3 na pasta da execucao que chamou esta funcao
        s3 = boto3.client('s3')
        nome_arquivo = f'tempo_cobrado-{ambiente}{dia_inicial}-{hora_inicial}-r{rodada}-{input_set}K-t{threads}.txt'
        nome_bucket = "INFORMAR"
        subpasta_dados="dados-containers"
        s3.put_object(Bucket=f'{nome_bucket}', Key=f'{subpasta_dados}/{ambiente}/{dia_inicial}-{hora_inicial}-r{rodada}-{input_set}K-t{threads}/{nome_arquivo}', Body=str(diferenca))

        #Incrementando a rodada para a próxima execução
        if threads < 8:
            threads *= 2
        elif input_set < 500:
            # quando 'threads' chega a 8, o 'input_set' é incrementado em 100 e 'threads' volta para 1
            threads = 1
            input_set += 100
        elif rodada < 3:
            # quando 'input_set' chega a 500, a 'rodada' é incrementada em 1 e 'input_set' volta para 100, assim como 'threads' volta para 1
            threads = 1
            input_set = 100
            rodada += 1
        else:
             # quando 'rodada' chega a 3, todas as combinações foram executadas e o experimento é finalizado
            print("Todas as combinações foram executadas.")
            
            # Invocando a função lambda que captura medias de tempo de execucao no ambiente em questao
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=f'captura-medias-tempo-{ambiente}',
                InvocationType='Event',  
                Payload=json.dumps({"ambiente": ambiente})
            )
            
            return
        
        parametros_execucao = {
            "AWS_ACCESS_KEY_ID": "INFORMAR",
            "AWS_SECRET_ACCESS_KEY": "INFORMAR",
            "AWS_DEFAULT_REGION": "us-east-1", 
            "RODADA": rodada,
            "THREADS": threads,
            "INPUT_SET": input_set 
        }


        # lançando a próxima tarefa no ECS
        run_task_params = {
            'cluster': cluster,
            'taskDefinition': task_info['taskDefinitionArn'],
            'overrides': {
                'containerOverrides': [
                    {
                        'name': task_info['containers'][0]['name'],
                        'environment': [
                            {'name': a, 'value': str(b)} for a, b in parametros_execucao.items()
                        ]
                    }
                ]
            },
            'launchType': ambiente,
        }

        if ambiente == "FARGATE":
            network_configuration = {
                'awsvpcConfiguration': {
                    'subnets': ['INFORMAR'],
                    'securityGroups': ['INFORMAR'], 
                    'assignPublicIp': 'ENABLED'
                }
            }

            run_task_params['networkConfiguration'] = network_configuration

        ecs.run_task(**run_task_params)

    except Exception as e:
        print("Erro:", str(e))