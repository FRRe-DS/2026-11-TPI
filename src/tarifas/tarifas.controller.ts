import { Controller, Get, Post, Body } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { TarifasService } from './tarifas.service';
import { CreateTarifaDto } from './dto/create-tarifa.dto';

@ApiTags('Tarifas')
@Controller('api/tarifas')
export class TarifasController {
  constructor(private readonly tarifasService: TarifasService) {}

  @Post('estimar')
  @ApiOperation({ summary: 'Estimar tarifa y registrarla (Consumido por M9)' })
  @ApiResponse({ status: 201, description: 'Tarifa estimada y guardada exitosamente.' })
  estimar(@Body() createTarifaDto: CreateTarifaDto) {
    return this.tarifasService.estimarTarifa(createTarifaDto);
  }

  @Get()
  @ApiOperation({ summary: 'Obtener el historial de tarifas estimadas' })
  @ApiResponse({ status: 200, description: 'Lista de tarifas estimadas devuelta exitosamente.' })
  findAll() {
    return this.tarifasService.obtenerTodas();
  }
}