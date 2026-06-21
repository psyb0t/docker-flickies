# flickies Go client

Typed Go client for the [flickies](https://github.com/psyb0t/docker-flickies)
HTTP API. Generated from `../../../openapi.yaml` via `oapi-codegen`.

## Install

```bash
go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest
```

## Usage

```go
import (
    "context"
    flickies "github.com/psyb0t/docker-flickies/pkg/clients/go"
)

client, _ := flickies.NewClient("http://localhost:8000")
resp, err := client.PostVideoLipsync(context.Background(), flickies.VideoLipsyncRequest{
    FacePath:        ptr("face.mp4"),
    AudioPathOrUrl:  "voice.wav",
    Engine:          ptr(flickies.VideoLipsyncRequestEngineLatentsync15),
    RestoreFace:     ptr(true),
    OutputPath:      ptr("out.mp4"),
})
```

## Regenerate

```bash
# from repo root
make generate-client-go
```

Never hand-edit `client.gen.go`. Edit `openapi.yaml`, then regenerate.

## License

WTFPL. See repo root.
