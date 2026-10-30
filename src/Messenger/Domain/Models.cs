namespace Messenger.Domain;

public interface IOrderedEntity
{
    Guid Id { get; }
    DateTime CreatedAt { get; }
}
public sealed record User(Guid Id, string Username, string DisplayName, DateTime CreatedAt) : IOrderedEntity;
public sealed record Chat(Guid Id, string Title, IReadOnlyList<Guid> MemberIds, DateTime CreatedAt) : IOrderedEntity;
public sealed record Message(Guid Id, Guid ChatId, Guid SenderId, string Text, DateTime CreatedAt) : IOrderedEntity;
public sealed record Page<T>(IReadOnlyList<T> Items, string? NextCursor);
public sealed record PageRequest(int Limit, string? Cursor);

// Business failures carry stable API codes, never exception details or user text.
public sealed class ApiException(int status, string code, string message) : Exception(message)
{
    public int Status { get; } = status;
    public string Code { get; } = code;
    public static ApiException Invalid() => new(400, "invalid_request", "Invalid request.");
    public static ApiException Unauthorized() => new(401, "unauthorized", "User identification required.");
    public static ApiException NotFound() => new(404, "not_found", "Object not found.");
}
