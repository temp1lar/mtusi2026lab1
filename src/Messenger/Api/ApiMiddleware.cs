using System.Diagnostics;
using System.Text.Json;
using Messenger.Domain;
namespace Messenger.Api;

public sealed class ApiMiddleware(RequestDelegate next, ILogger<ApiMiddleware> logger)
{
    public async Task InvokeAsync(HttpContext ctx, IHostApplicationLifetime life)
    {
        var requestId = Guid.NewGuid().ToString("N");
        ctx.Response.Headers["X-Request-Id"] = requestId;
        var started = Stopwatch.GetTimestamp();
        try
        {
            if (life.ApplicationStopping.IsCancellationRequested)
                throw new ApiException(503, "unavailable", "Stopping.");
            await next(ctx);
        }
        catch (ApiException ex) { await Error(ctx, ex.Status, ex.Code, ex.Message, requestId); }
        catch (JsonException) { await Error(ctx, 400, "invalid_request", "Invalid JSON.", requestId); }
        catch (BadHttpRequestException ex)
        {
            var large = ex.StatusCode == 413;
            await Error(ctx, large ? 413 : 400, large ? "payload_too_large" : "invalid_request", "Invalid request body.", requestId);
        }
        catch (OperationCanceledException) when (ctx.RequestAborted.IsCancellationRequested) { }
        catch (Exception ex)
        {
            // Exception messages can contain input. Log only the type, not the body/stack.
            logger.LogError("Unhandled {ExceptionType}; request_id={RequestId}", ex.GetType().Name, requestId);
            await Error(ctx, 500, "internal_error", "Internal server error.", requestId);
        }
        finally
        {
            var route = (ctx.GetEndpoint() as RouteEndpoint)?.RoutePattern.RawText ?? "unmatched";
            logger.LogInformation("HTTP {Method} {Route} status={Status} elapsed_ms={Elapsed:F2} request_id={RequestId}",
                ctx.Request.Method, route, ctx.Response.StatusCode, Stopwatch.GetElapsedTime(started).TotalMilliseconds, requestId);
        }
    }
    private static Task Error(HttpContext ctx, int status, string code, string message, string id)
    {
        ctx.Response.StatusCode = status;
        return ctx.Response.WriteAsJsonAsync(new { error = new { code, message, request_id = id } });
    }
}
