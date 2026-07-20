# lab-devices → lab_devices_server bump dispatch

Applied in `bioexperiment-lab-devices/lab-devices`, not this repo. Add to that
repo's `.github/workflows/release-please.yml`:

```yaml
  dispatch-bump:
    needs: [release-please, image]
    if: ${{ needs.release-please.outputs.release_created == 'true' }}
    runs-on: ubuntu-latest
    steps:
      - id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}
          # Required: without these the token is scoped to lab-devices only.
          owner: bioexperiment-lab-devices
          repositories: lab_devices_server
      - env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          TAG: ${{ needs.release-please.outputs.tag_name }}
        run: |
          gh workflow run image-bump.yml \
            -R bioexperiment-lab-devices/lab_devices_server \
            -f service=studio \
            -f version="${TAG#v}"
```

`needs: image` is required, not stylistic: `images.sh` probes the registry
before it commits, so dispatching before the GHCR push completes would fail on
a tag that does not yet exist.

## Manual prerequisite

The org App behind `RELEASE_PLEASE_APP_ID` needs **Actions: read & write**, and
its installation must cover both repos. If the grant is missing the dispatch
step fails with a 403 and no bump PR is opened — a loud failure, not a silent
one.
