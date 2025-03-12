import boto3
import json
from datetime import datetime
import time


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
    # },
    # {
    #     "Effect": "Allow",
    #     "Action": [
    #         "ecs:ListTaskDefinitions",
    #         "ecs:DescribeTaskDefinition"
    #     ],
    #     "Resource": INFORMAR
    # }

#Obs.: no campo "INFORMAR", pode-se adicionar um "*" para que valha para qualquer recurso


def lambda_handler(event, context):
    try:
        ecs = boto3.client('ecs')
        
        arn_tarefa = event.get('arn_tarefa')
        cluster = event.get('cluster')
        ambiente = event.get('ambiente')
        identificacao = event.get('identificacao')
        input_set = int(event.get('input_set', 0))
        rodada = int(event.get('rodada', 0))
        quant_containers = int(event.get('quant_containers', 0))

        print("Dados:")
        print("arn tarefa: ", arn_tarefa)
        print("cluster: ", cluster)
        print("ambiente:", ambiente)
        print("identificacao: ", identificacao)
        print("input set", input_set)
        print("rodada", rodada)
        print("qtd containers", quant_containers)


        resp = ecs.describe_tasks(
            cluster=cluster,
            tasks=[arn_tarefa]
        )

        tarefa = resp['tasks'][0]

        #consultando os tempos inicial e final de cobranca
        t_inicio = tarefa.get('pullStartedAt', '')
        t_fim = tarefa.get('executionStoppedAt', '')
        while not (t_inicio and t_fim):
            resp = ecs.describe_tasks(
                cluster=cluster,
                tasks=[arn_tarefa]
            )

            tarefa = resp['tasks'][0]

            t_inicio = tarefa.get('pullStartedAt', '')
            t_fim = tarefa.get('executionStoppedAt', '')


        diferenca = t_fim - t_inicio


        #enviando tempo de execucao ao s3
        s3 = boto3.client('s3')
        nome_arquivo = f'tempo_cobrado-{ambiente}-{identificacao}-{input_set}K-r{rodada}-{quant_containers}-c.txt'
        nome_bucket = "INFORMAR"
        subpasta_dados="dados-containers"
        s3.put_object(Bucket=f'{nome_bucket}', Key=f'{subpasta_dados}/{ambiente}/{quant_containers}c-{input_set}K/{identificacao}-r{rodada}/{nome_arquivo}', Body=str(diferenca))

        # incrementando a rodada para a próxima execucao
        if quant_containers < 4:
            quant_containers *= 2
        elif input_set < 400:
            quant_containers = 1
            input_set += 100
        elif rodada < 3:
            quant_containers = 1
            input_set = 200  
            rodada += 1
        else:
            print("Todas as combinações foram executadas.")
            
            # invocando a função lambda captura-medias-tempo
            cliente_lambda = boto3.client('lambda')
            nome_funcao = f'ERAD-captura-medias-tempo-{ambiente}'
        
            cliente_lambda.invoke(
                FunctionName=nome_funcao,
                InvocationType='Event',  
                Payload=json.dumps({"ambiente": ambiente})
            )
            
            return

        parametros_sobreescritos = {
            "RODADA": rodada,
            "INPUT_SET": input_set 
        }

        if quant_containers == 1:
            definicao_tarefa = f'1-CONTAINER-{ambiente}'
        else:
            definicao_tarefa = f'{quant_containers}-CONTAINERS-{ambiente}'

        # obtendo a definição mais recente da tarefa
        resp = ecs.list_task_definitions(
            familyPrefix=definicao_tarefa,
            sort='DESC',
            maxResults=1
        )

        definicao_tarefa_mais_recente = resp['taskDefinitionArns'][0]
        print("Definição da tarefa mais recente:", definicao_tarefa_mais_recente)

        # Preparando a lista de sobrescrita de variáveis para cada container
        container_overrides = []
        for i in range(quant_containers):
            container_name = f"container-{i}"
            container_overrides.append({
                'name': container_name,
                'environment': [
                    {'name': a, 'value': str(b)} for a, b in parametros_sobreescritos.items()
                ]
            })

        run_task_params = {
            'cluster': cluster,
            'taskDefinition': definicao_tarefa_mais_recente,
            'overrides': {
                'containerOverrides': container_overrides  # obrescreve as variáveis para todos os containers
            },
            'launchType': ambiente,
        }

        # configuração de rede para o Fargate
        if ambiente == "FARGATE":
            network_configuration = {
                'awsvpcConfiguration': {
                    'subnets': ['subnet-0452e487391512e2b'],
                    'securityGroups': ['sg-0071ad348c931b62c'], 
                    'assignPublicIp': 'ENABLED'
                }
            }
            run_task_params['networkConfiguration'] = network_configuration

        while True:
            response = ecs.describe_tasks(cluster=cluster, tasks=[arn_tarefa])
            tarefa = response['tasks'][0]
            status = tarefa['lastStatus']
            if status == 'STOPPED':
                break
            time.sleep(10) 

        try:
            response = ecs.run_task(**run_task_params)
            print("Tarefa lançada com sucesso:", response)
        except Exception as e:
            print("Erro ao lançar a tarefa:", str(e))


    except Exception as e:
        print("Erro:", str(e))