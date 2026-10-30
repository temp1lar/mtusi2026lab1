using Messenger.Domain;
using Messenger.Storage;
namespace Messenger.Api;

public static class Endpoints
{
    public static void MapMessenger(this WebApplication app)
    {
        app.MapGet("/health/live", () => Results.Ok(new { status = "ok" }));
        app.MapGet("/health/ready", (IHostApplicationLifetime life) =>
        {
            if (life.ApplicationStopping.IsCancellationRequested) throw new ApiException(503, "unavailable", "Stopping.");
            return Results.Ok(new { status = "ok" });
        });
        app.MapPost("/api/v1/users", async (HttpContext ctx, IMessengerStore store) =>
        {
            using var body = await Input.Body(ctx.Request, "username", "display_name");
            var user = await store.CreateUserAsync(Input.Username(body.RootElement), Input.Text(body.RootElement, "display_name", 100));
            return Results.Json(user, statusCode: 201);
        });
        app.MapGet("/api/v1/users/me", async (HttpContext ctx, ICurrentUser current) => Results.Ok(await current.RequireAsync(ctx)));
        app.MapPost("/api/v1/chats", async (HttpContext ctx, ICurrentUser current, IMessengerStore store) =>
        {
            var actor = await current.RequireAsync(ctx);
            using var body = await Input.Body(ctx.Request, "title", "member_ids");
            var chat = await store.CreateChatAsync(actor.Id, Input.Text(body.RootElement, "title", 100), Input.Members(body.RootElement));
            return Results.Json(chat, statusCode: 201);
        });
        app.MapGet("/api/v1/chats", async (HttpContext ctx, ICurrentUser current, IMessengerStore store) =>
        {
            var actor = await current.RequireAsync(ctx);
            return Results.Ok(await store.ListChatsAsync(actor.Id, Input.Page(ctx.Request)));
        });
        app.MapGet("/api/v1/chats/{chat_id}", async (string chat_id, HttpContext ctx, ICurrentUser current, IMessengerStore store) =>
        {
            var actor = await current.RequireAsync(ctx);
            return Results.Ok(await store.GetChatAsync(actor.Id, Input.Id(chat_id)));
        });
        app.MapGet("/api/v1/chats/{chat_id}/messages", async (string chat_id, HttpContext ctx, ICurrentUser current, IMessengerStore store) =>
        {
            var actor = await current.RequireAsync(ctx);
            var id = Input.Id(chat_id);
            await store.GetChatAsync(actor.Id, id); // Access before parsing query.
            return Results.Ok(await store.ListMessagesAsync(actor.Id, id, Input.Page(ctx.Request)));
        });
        app.MapPost("/api/v1/chats/{chat_id}/messages", async (string chat_id, HttpContext ctx, ICurrentUser current, IMessengerStore store) =>
        {
            var actor = await current.RequireAsync(ctx);
            var id = Input.Id(chat_id);
            await store.GetChatAsync(actor.Id, id); // A stranger must not learn anything from body validation.
            using var body = await Input.Body(ctx.Request, "text");
            return Results.Json(await store.AddMessageAsync(actor.Id, id, Input.Text(body.RootElement, "text", 4000)), statusCode: 201);
        });
        app.MapFallback((HttpContext _) => Task.FromException(ApiException.NotFound()));
    }
}
