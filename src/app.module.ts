import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { MetodosPagoModule } from './metodos-pago/metodos-pago.module';
import { PagosModule } from './pagos/pagos.module';
import { TarifasModule } from './tarifas/tarifas.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        type: 'mysql',
        host: configService.get<string>('DB_HOST', 'localhost'),
        port: configService.get<number>('DB_PORT', 3306),
        username: configService.get<string>('DB_USER', 'root'),
        password: configService.get<string>('DB_PASSWORD', 'rootpassword'),
        database: configService.get<string>('DB_NAME', 'universidad_db'),
        autoLoadEntities: true,
        synchronize: true, // Crea/actualiza las tablas automáticamente en desarrollo local
      }),
    }),
    MetodosPagoModule,
    PagosModule,
    TarifasModule,
  ],
})
export class AppModule {}