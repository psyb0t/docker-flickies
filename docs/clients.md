---
title: "Generated clients"
description: "Install and use the Go and Python flickies clients generated from openapi.yaml, add auth, and work around the request fields the generators drop."
nav_order: 8
---

# Generated clients

[openapi.yaml](https://github.com/psyb0t/docker-flickies/blob/main/openapi.yaml) describes every REST route, and two clients are generated from it and committed to the repository:

| Client | Location | Generator |
| --- | --- | --- |
| Go | [pkg/clients/go/](https://github.com/psyb0t/docker-flickies/tree/main/pkg/clients/go) | oapi-codegen |
| Python | [pkg/clients/python/flickies-client/](https://github.com/psyb0t/docker-flickies/tree/main/pkg/clients/python/flickies-client) | openapi-python-client |

Server-side Pydantic models in `src/flickies/schema/_generated.py` come from the same file. To regenerate any of them, see [Development](development.md#code-generation).

## Known gap: request types lose their fields

Most request schemas in `openapi.yaml` combine `allOf` references with their own `properties`, and the generators drop some or all of those own properties. The generated request types are missing these fields:

| Request | Go client | Python client |
| --- | --- | --- |
| lipsync | `face_path`, `face_url`, `audio_path`, `audio_url`, `engine`, `restore_face` | same as Go |
| concat | `inputs_paths`, `inputs_urls`, `precise` | same as Go |
| mux audio | `video_path_or_url`, `audio_path_or_url`, `replace_existing_audio` | same as Go |
| extract audio | `audio_format`, `output_path`, `output_url` | same as Go |
| thumbnail grid | `rows`, `cols`, `cell_width`, `cell_height`, `output_path`, `output_url` | same as Go |
| trim | `start_sec`, `end_sec`, `precise` | complete |
| transcode | `video_codec`, `audio_codec`, `crf`, `preset`, `fps`, `gif_options` | complete |
| scale | `width`, `height`, `keep_aspect` | complete |
| restore | `engine` (the server ignores it anyway) | complete |
| info | complete | complete |

Responses, health, engines, files and jobs are complete in both. For the missing fields, send your own JSON as shown below.

## Go

```bash
go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest
```

The package name is `flickiesclient`. Typed methods work for health, engines, files, jobs, info and restore. For every other video route, use the route's `...WithBody` method and send the JSON yourself:

```go
package main

import (
	"context"
	"io"
	"log"
	"strings"

	flickies "github.com/psyb0t/docker-flickies/pkg/clients/go"
)

func main() {
	c, err := flickies.NewClient("http://localhost:8000")
	if err != nil {
		log.Fatal(err)
	}

	body := strings.NewReader(`{
  "file_path": "uploads/clip.mp4",
  "start_sec": 2,
  "end_sec": 7,
  "precise": true,
  "output_path": "out/clip-trimmed.mp4"
}`)

	resp, err := c.PostVideoTrimWithBody(context.Background(), "application/json", body)
	if err != nil {
		log.Fatal(err)
	}
	defer resp.Body.Close()

	out, _ := io.ReadAll(resp.Body)
	log.Println(resp.StatusCode, string(out))
}
```

Add the bearer token with a request editor:

```go
c, err := flickies.NewClient(
	"http://localhost:8000",
	flickies.WithRequestEditorFn(func(_ context.Context, req *http.Request) error {
		req.Header.Set("Authorization", "Bearer "+token)
		return nil
	}),
)
```

## Python

```bash
pip install "git+https://github.com/psyb0t/docker-flickies.git#subdirectory=pkg/clients/python/flickies-client"
```

Trim, transcode, scale, restore and info have complete models. The generated models also keep unknown keys and send them, so build an incomplete type with `from_dict` and the missing fields are passed through:

```python
from flickies_client import AuthenticatedClient
from flickies_client.api.lipsync import post_video_lipsync
from flickies_client.models import BaseVideoOutputRequest

client = AuthenticatedClient(base_url="http://localhost:8000", token="testme")

body = BaseVideoOutputRequest.from_dict(
    {
        "face_path": "uploads/face.mp4",
        "audio_path": "uploads/voice.wav",
        "engine": "latentsync-1.5",
        "output_path": "out/talking.mp4",
    }
)

result = post_video_lipsync.sync(client=client, body=body)
print(result)
```

Use `Client(base_url=...)` instead of `AuthenticatedClient` when auth is off. Each operation module has `sync`, `sync_detailed`, `asyncio` and `asyncio_detailed`.
