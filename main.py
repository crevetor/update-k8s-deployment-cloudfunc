def get_kube_client(project, zone, cluster):
    BASE_URL = 'https://container.googleapis.com/v1beta1/'

    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    if not credentials.valid:
        credentials.refresh(google.auth.transport.requests.Request())

    authed_session = google.auth.transport.requests.AuthorizedSession(credentials)
    res = authed_session.get(f'{BASE_URL}projects/{project}/locations/{zone}/clusters/{cluster}')

    res.raise_for_status()

    cluster_info = res.json()

    config = kubernetes.client.Configuration()

    config.host = f"https://{cluster_info['endpoint']}"
    config.verify_ssl = False
    config.api_key = {"authorization": f'Bearer {credentials.token}'}
    client = kubernetes.client.ApiClient(config)

    return kubernetes.client.AppsV1Api(client)

def onNewImage(data, context):
    import base64
    import json
    import kubernetes
    import google.auth
    import os
    import tempfile
    import logging

    project = os.environ.get('PROJECT')
    zone = os.environ.get('ZONE')
    cluster = os.environ.get('CLUSTER')
    deployment = os.environ.get('DEPLOYMENT')
    deploy_image = os.environ.get('IMAGE')
    target_container = os.environ.get('CONTAINER')

    if 'data' not in data:
        logging.error('No data key in data dict')
        return

    decoded_data = json.loads(base64.b64decode(data['data']).decode('utf-8'))
    logging.info(f'Decoded data : {decoded_data}')
    if decoded_data.get('action', None) is None:
        logging.error('No action key in data')
        return

    image = decoded_data.get('digest', None)
    if image is None:
        logging.error('No digest key in data')
        return

    image_basename = image.split('/')[-1].split('@')[0]
    if image_basename != deploy_image:
        logging.error(f'{image_basename} is different from {deploy_image}')
        return

    v1 = get_kube_client(project, zone, cluster)
    dep = v1.read_namespaced_deployment(deployment, 'default')
    if dep is None:
        logging.error(f'There was no deployment named {deployment}')
        return

    for i, container in enumerate(dep.spec.template.spec.containers):
        if container.name == 'flask':
            dep.spec.template.spec.containers[i].image = image
    logging.info(f'Updating to {image}')
    v1.patch_namespaced_deployment(deployment, 'default', dep)
