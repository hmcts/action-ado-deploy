# Deployment via ADO Pipeline

GitHub Action that updates a service image tag in a deployment config repo, triggers an Azure DevOps pipeline, and optionally waits for it to finish.

## How it works

1. Checks that you provided auth credentials (GitHub App or SSH deploy key)
2. Clones the target repo and updates the service's image tag in the values YAML
3. Commits and pushes if anything changed
4. Triggers the ADO pipeline with your template parameters
5. Polls for completion (unless `wait` is `false`)

## Usage

### With GitHub App authentication

```yaml
- uses: hmcts/action-ado-deploy@v1
  with:
    service_name: my-service
    image_tag: sha-abc1234
    target_repository: hmcts/deployment-config
    target_branch: main
    values_file: services/values.yaml
    app_id: ${{ secrets.APP_ID }}
    app_private_key: ${{ secrets.APP_PRIVATE_KEY }}
    pipeline_id: '42'
    ado_pat: ${{ secrets.ADO_PAT }}
    template_parameters: '{"environment": "staging", "service": "my-service"}'
```

### With SSH deploy key

```yaml
- uses: hmcts/action-ado-deploy@v1
  with:
    service_name: my-service
    image_tag: sha-abc1234
    target_repository: hmcts/deployment-config
    target_branch: main
    values_file: services/values.yaml
    deploy_key: ${{ secrets.DEPLOY_KEY }}
    pipeline_id: '42'
    ado_pat: ${{ secrets.ADO_PAT }}
    template_parameters: '{"environment": "staging", "service": "my-service"}'
```

### Fire-and-forget (don't wait for pipeline)

```yaml
- uses: hmcts/action-ado-deploy@v1
  with:
    service_name: my-service
    image_tag: sha-abc1234
    target_repository: hmcts/deployment-config
    target_branch: main
    values_file: services/values.yaml
    deploy_key: ${{ secrets.DEPLOY_KEY }}
    pipeline_id: '42'
    ado_pat: ${{ secrets.ADO_PAT }}
    template_parameters: '{"environment": "staging"}'
    wait: 'false'
```

## Inputs

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `service_name` | Yes | | Service name as it appears in the services values file |
| `image_tag` | Yes | | New image tag to set for the service |
| `target_repository` | Yes | | GitHub repository containing the deployment config (owner/repo) |
| `target_branch` | Yes | | Branch to update in the target repository |
| `values_file` | Yes | | Path to the services values YAML file within the target repository |
| `app_id` | No | `''` | GitHub App ID for generating an installation token |
| `app_private_key` | No | `''` | GitHub App private key for generating an installation token |
| `deploy_key` | No | `''` | SSH deploy key for authentication to the target repository |
| `ado_org` | No | `hmcts-cpp` | Azure DevOps organisation name |
| `ado_project` | No | `cpp-apps` | Azure DevOps project name |
| `pipeline_id` | Yes | | ID of the Azure DevOps deployment pipeline to trigger |
| `ado_pat` | Yes | | Azure DevOps Personal Access Token |
| `template_parameters` | Yes | | JSON string of template parameters for the pipeline |
| `ref_name` | No | `refs/heads/main` | Git reference (branch) for the triggered pipeline |
| `api_version` | No | `7.0` | Azure DevOps API version |
| `poll_interval` | No | `30` | Seconds between status checks |
| `timeout` | No | `1800` | Max seconds to wait for pipeline completion (30 min) |
| `wait` | No | `true` | Whether to wait for the pipeline to complete |

## Outputs

| Name | Description |
|------|-------------|
| `run_id` | The ID of the triggered pipeline run |
| `result` | Pipeline result (`succeeded`, `failed`, or `canceled`) |

## Authentication

Pick one:

- `app_id` + `app_private_key` -- the action generates a scoped installation token from your GitHub App.
- `deploy_key` -- an SSH private key with write access to the target repo.

## Prerequisites

The runner needs:

- Python 3 with `requests`
- `yq`
- `git` and `ssh`

## License

MIT -- see [LICENSE](LICENSE) for details.
