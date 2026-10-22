import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { TarifasService } from './tarifas.service';
import { TarifasController } from './tarifas.controller';
import { TarifaEstimada } from './entities/tarifa-estimada.entity';

@Module({
  imports: [TypeOrmModule.forFeature([TarifaEstimada])],
  controllers: [TarifasController],
  providers: [TarifasService],
})
export class TarifasModule {}