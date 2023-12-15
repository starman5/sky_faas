'''
This is a Hello World example, for easy demonstration of the correctness of SkyFaaS
'''

def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello, World!'
    }

