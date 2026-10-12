FROM maven:3.9.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY backend/pom.xml backend/pom.xml
COPY backend/kaoyan-common backend/kaoyan-common
COPY backend/kaoyan-pojo backend/kaoyan-pojo
COPY backend/kaoyan-server backend/kaoyan-server
RUN mvn -f backend/pom.xml -B -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /build/backend/kaoyan-server/target/kaoyan-server-0.1.0.jar app.jar
RUN useradd -r -u 10001 agent && chown agent /app
USER agent
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
