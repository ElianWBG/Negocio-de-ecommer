import datetime

from django.core.exceptions import ValidationError


def parse_date_param(value):
    """Convierte un parámetro de fecha de un ?date_from=/date_to= de GET
    (formato YYYY-MM-DD) a un date, o None si viene vacío o mal formado.

    Pensado para filtros opcionales: un valor inválido simplemente se trata
    como "sin filtro" en vez de dejar que el ValueError/ValidationError del
    ORM tumbe la vista con un 500.
    """
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def validate_cedula_ec(value):
    """
    Valida cédula ecuatoriana (10 dígitos) o RUC (13 dígitos)
    usando el algoritmo oficial del Registro Civil de Ecuador.
    
    Algoritmo:
    1. La cédula tiene 10 dígitos
    2. Los 2 primeros dígitos son el código de provincia (01-24)
    3. El tercer dígito debe ser menor a 6
    4. Se multiplican los dígitos alternadamente por 2 y 1
    5. Si el resultado > 9, se resta 9
    6. Se suman todos los resultados
    7. El dígito verificador = (decena superior - suma) mod 10
    
    Uso en modelo:
        from shared.validators import validate_cedula_ec
        dni = CharField(validators=[validate_cedula_ec])
    
    Ejemplo:
        validate_cedula_ec("0912345678")  # Válida o lanza error
    """

    # --- Paso 1: Verificar que solo contenga números ---
    if not (value.isascii() and value.isdigit()):
        raise ValidationError(
            'The ID must contain only numbers.',
            code='invalid_chars'
        )

    # --- Paso 2: Verificar longitud ---
    # Cédula = 10 dígitos, RUC = 13 dígitos
    if len(value) not in (10, 13):
        raise ValidationError(
            'The ID must be 10 digits (cédula) or 13 digits (RUC).',
            code='invalid_length'
        )

    # --- Paso 3: Verificar código de provincia ---
    # Los 2 primeros dígitos = provincia (01 a 24)
    province = int(value[:2])
    if province < 1 or province > 24:
        raise ValidationError(
            f'Invalid province code: {province}. Must be between 01 and 24.',
            code='invalid_province'
        )

    # --- Paso 4: Verificar tercer dígito y aplicar el algoritmo que le
    # corresponde. Un RUC (13 dígitos) puede ser de:
    #   - persona natural (tercer dígito 0-5): mismo algoritmo que la cédula.
    #   - sociedad privada (tercer dígito 9): módulo 11 sobre 9 dígitos.
    #   - entidad pública (tercer dígito 6): módulo 11 sobre 8 dígitos.
    # Antes solo se aceptaba el primer caso, rechazando todo RUC de empresa.
    third_digit = int(value[2])
    digits = [int(c) for c in value]

    if third_digit < 6:
        # --- Módulo 10 (cédula, o los primeros 10 dígitos de un RUC de persona natural) ---
        coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i in range(9):
            result = digits[i] * coefficients[i]
            if result > 9:
                result -= 9
            total += result
        verifier = 10 - (total % 10)
        if verifier == 10:
            verifier = 0
        if verifier != digits[9]:
            raise ValidationError(
                'Invalid ID number. The check digit does not match.',
                code='invalid_verifier'
            )
    elif len(value) == 13 and third_digit == 9:
        # --- Módulo 11, sociedad privada: coeficientes sobre los primeros 9 dígitos ---
        coefficients = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(digits[i] * coefficients[i] for i in range(9))
        verifier = 11 - (total % 11)
        if verifier == 11:
            verifier = 0
        if verifier == 10 or verifier != digits[9]:
            raise ValidationError(
                'Invalid ID number. The check digit does not match.',
                code='invalid_verifier'
            )
    elif len(value) == 13 and third_digit == 6:
        # --- Módulo 11, entidad pública: coeficientes sobre los primeros 8 dígitos ---
        coefficients = [3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(digits[i] * coefficients[i] for i in range(8))
        verifier = 11 - (total % 11)
        if verifier == 11:
            verifier = 0
        if verifier == 10 or verifier != digits[8]:
            raise ValidationError(
                'Invalid ID number. The check digit does not match.',
                code='invalid_verifier'
            )
    else:
        raise ValidationError(
            'The third digit must be less than 6 for natural persons, or 6/9 for a company RUC.',
            code='invalid_third'
        )

    return value
