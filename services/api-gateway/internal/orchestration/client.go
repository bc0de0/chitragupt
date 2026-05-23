// Package orchestration provides a gRPC client for the Python AiOrchestration service.
package orchestration

import (
	"context"
	"fmt"
	"io"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	commonpb "github.com/bc0de0/chitragupt/services/api-gateway/proto/common"
	orchpb "github.com/bc0de0/chitragupt/services/api-gateway/proto/orchestration"
)

// Client wraps the AiOrchestration gRPC client.
type Client struct {
	conn   *grpc.ClientConn
	client orchpb.AiOrchestrationClient
}

// NewClient dials the Python orchestration service and returns a Client.
func NewClient(addr string) (*Client, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(ctx, addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("dial orchestration %s: %w", addr, err)
	}
	return &Client{conn: conn, client: orchpb.NewAiOrchestrationClient(conn)}, nil
}

// Close releases the underlying connection.
func (c *Client) Close() error {
	return c.conn.Close()
}

// PipelineResult carries the complete outcome of one RunPipeline call.
type PipelineResult struct {
	Tokens    []string
	Complete  *orchpb.TurnComplete
}

// RunPipeline calls AiOrchestration.RunPipeline and collects all events.
// onToken is called for each streaming token so the caller can forward to SSE.
func (c *Client) RunPipeline(
	ctx context.Context,
	sessionState *commonpb.SessionStateProto,
	userMessage string,
	onToken func(string),
) (*PipelineResult, error) {
	stream, err := c.client.RunPipeline(ctx, &orchpb.PipelineRequest{
		SessionState: sessionState,
		UserMessage:  userMessage,
	})
	if err != nil {
		return nil, fmt.Errorf("RunPipeline: %w", err)
	}

	result := &PipelineResult{}

	for {
		event, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return result, fmt.Errorf("RunPipeline stream: %w", err)
		}

		switch e := event.Event.(type) {
		case *orchpb.PipelineEvent_Token:
			result.Tokens = append(result.Tokens, e.Token)
			if onToken != nil {
				onToken(e.Token)
			}
		case *orchpb.PipelineEvent_Complete:
			result.Complete = e.Complete
		}
	}

	return result, nil
}

// IngestDocument sends a document to Python for background processing.
func (c *Client) IngestDocument(
	ctx context.Context,
	req *orchpb.IngestRequest,
) (*orchpb.IngestResponse, error) {
	return c.client.IngestDocument(ctx, req)
}

// Healthz probes the Python service.
func (c *Client) Healthz(ctx context.Context) (string, error) {
	resp, err := c.client.Healthz(ctx, &orchpb.HealthRequest{})
	if err != nil {
		return "", err
	}
	return resp.Status, nil
}
