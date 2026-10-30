using System.Text.Json;
using Messenger.Api;
using Messenger.Storage;

// A built-in health probe avoids installing curl and extra packages into runtime.
if (args.Contains("--healthcheck"))
{
    try
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        var port = Environment.GetEnvironmentVariable("APP_PORT") ?? "8080";
        var response = await client.GetAsync($"http://127.0.0.1:{port}/health/ready");
        return response.IsSuccessStatusCode ? 0 : 1;
    }
    catch { return 1; }
}
var builder = WebApplication.CreateBuilder(args);
var host = builder.Configuration["APP_HOST"] ?? "0.0.0.0";
var portText = builder.Configuration["APP_PORT"] ?? "8080";
if (!int.TryParse(portText, out var appPort) || appPort is < 1 or > 65535)
    throw new InvalidOperationException("APP_PORT must be 1..65535.");
builder.WebHost.UseUrls($"http://{host}:{appPort}");
builder.WebHost.ConfigureKestrel(options => options.Limits.MaxRequestBodySize = 1024 * 1024);
builder.Services.Configure<HostOptions>(options => options.ShutdownTimeout = TimeSpan.FromSeconds(5));
builder.Services.ConfigureHttpJsonOptions(options => options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower);
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole();
builder.Logging.AddFilter("Microsoft.AspNetCore", LogLevel.Warning);
builder.Services.AddSingleton<CursorCodec>();
builder.Services.AddSingleton<IMessengerStore, InMemoryMessengerStore>();
builder.Services.AddSingleton<ICurrentUser, HeaderCurrentUser>();
var app = builder.Build();
app.UseMiddleware<ApiMiddleware>();
app.MapMessenger();
app.Logger.LogInformation("Messenger starting; app_env={Environment}", builder.Configuration["APP_ENV"] ?? "lab");
await app.RunAsync();
return 0;
