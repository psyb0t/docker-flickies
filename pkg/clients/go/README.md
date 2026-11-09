# flickies Go client

Typed Go client for the [flickies](https://github.com/psyb0t/docker-flickies)
HTTP API. Generated from `../../../openapi.yaml` via `oapi-codegen`.

## Install

```bash
go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest
```

## Usage

The package name is `flickiesclient`. Most generated request types are
missing their endpoint-specific fields (`face_path`, `start_sec`, `width`
and so on), because oapi-codegen drops the `properties` that sit next to
an `allOf` in `openapi.yaml`. Typed methods work for health, engines,
files, jobs, info and restore. For the other video routes, call the
`...WithBody` method and send the JSON yourself:

```go
package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	flickies "github.com/psyb0t/docker-flickies/pkg/clients/go"
)

func main() {
	token := os.Getenv("FLICKIES_AUTH_TOKEN")

	client, err := flickies.NewClient(
		"http://localhost:8000",
		flickies.WithRequestEditorFn(func(_ context.Context, req *http.Request) error {
			if token != "" {
				req.Header.Set("Authorization", "Bearer "+token)
			}
			return nil
		}),
	)
	if err != nil {
		log.Fatal(err)
	}

	body := strings.NewReader(`{
  "face_path": "uploads/face.mp4",
  "audio_path": "uploads/voice.wav",
  "engine": "latentsync-1.5",
  "output_path": "out/talking.mp4"
}`)

	resp, err := client.PostVideoLipsyncWithBody(context.Background(), "application/json", body)
	if err != nil {
		log.Fatal(err)
	}
	defer resp.Body.Close()

	out, _ := io.ReadAll(resp.Body)
	log.Println(resp.StatusCode, string(out))
}
```

Full docs: <https://psyb0t.github.io/docker-flickies/clients/>

## Regenerate

```bash
# from repo root
make generate-client-go
```

Never hand-edit `client.gen.go`. Edit `openapi.yaml`, then regenerate.

## License

WTFPL. See repo root.
