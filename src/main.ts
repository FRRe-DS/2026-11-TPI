import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Configuración de OpenAPI (Swagger)
  const config = new DocumentBuilder()
    .setTitle('API Módulo 7 - Tarifas, Pagos y Liquidaciones')
    .setDescription('Documentación de la API para estimación, cobro y liquidación de viajes.')
    .setVersion('1.0')
    .build();
    
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/docs', app, document);

  // Habilitamos CORS y escuchamos en el puerto configurado
  app.enableCors();
  await app.listen(process.env.PORT || 3000, '0.0.0.0');
}
bootstrap();