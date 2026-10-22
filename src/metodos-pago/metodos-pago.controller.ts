import { Controller, Get, Post, Body, Param } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiParam } from '@nestjs/swagger';
import { MetodosPagoService } from './metodos-pago.service';
import { CreateMetodoPagoDto } from './dto/create-metodo-pago.dto';

@ApiTags('Métodos de Pago')
@Controller('api/metodos-pago')
export class MetodosPagoController {
  constructor(private readonly metodosPagoService: MetodosPagoService) {}

  @Post()
  @ApiOperation({ summary: 'Registrar un nuevo método de pago' })
  @ApiResponse({ status: 201, description: 'Método de pago registrado exitosamente.' })
  registrar(@Body() createMetodoPagoDto: CreateMetodoPagoDto) {
    return this.metodosPagoService.registrar(createMetodoPagoDto);
  }

  @Get('cliente/:idCliente')
  @ApiOperation({ summary: 'Obtener los métodos de pago de un cliente' })
  @ApiParam({ name: 'idCliente', description: 'ID del cliente' })
  @ApiResponse({ status: 200, description: 'Lista de métodos devuelta exitosamente.' })
  obtenerPorCliente(@Param('idCliente') idCliente: string) {
    return this.metodosPagoService.obtenerPorCliente(idCliente);
  }
}