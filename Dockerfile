FROM mcr.microsoft.com/dotnet/sdk:10.0.403 AS build
WORKDIR /source
COPY global.json ./
COPY src/Messenger/Messenger.csproj src/Messenger/packages.lock.json ./src/Messenger/
RUN dotnet restore src/Messenger/Messenger.csproj --locked-mode
COPY src/ ./src/
RUN dotnet publish src/Messenger/Messenger.csproj -c Release --no-restore -o /out /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0.14 AS runtime
WORKDIR /app
COPY --from=build /out ./
ENV APP_HOST=0.0.0.0 APP_PORT=8080 APP_ENV=lab DOTNET_EnableDiagnostics=0
USER $APP_UID
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 CMD ["dotnet", "Messenger.dll", "--healthcheck"]
ENTRYPOINT ["dotnet", "Messenger.dll"]
