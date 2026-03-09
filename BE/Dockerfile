<<<<<<< HEAD
FROM eclipse-temurin:21-jdk AS build
WORKDIR /app

COPY gradle gradle
COPY gradlew settings.gradle build.gradle ./
RUN chmod +x gradlew
COPY src src

RUN ./gradlew bootJar --no-daemon

FROM eclipse-temurin:21-jdk
WORKDIR /app

COPY --from=build /app/build/libs/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
=======
FROM eclipse-temurin:21-jdk AS builder
WORKDIR /workspace

COPY gradlew ./
COPY gradle ./gradle
COPY build.gradle settings.gradle ./
COPY src ./src

RUN chmod +x gradlew && ./gradlew clean bootJar -x test

FROM eclipse-temurin:21-jre
WORKDIR /app

COPY --from=builder /workspace/build/libs/*.jar /app/app.jar

EXPOSE 8080
ENV JAVA_OPTS=""

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]
>>>>>>> main
