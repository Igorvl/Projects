


    $(function () {
		
		
		
		
        /*
         * queryParameters -> handles the query string parameters
         * queryString -> the query string without the fist '?' character
         * re -> the regular expression
         * m -> holds the string matching the regular expression
         */
        var queryParameters = {}, queryString = location.search.substring(1),
                re = /([^&=]+)=([^&]*)/g, m;

        // Creates a map with the query string parameters
        while (m = re.exec(queryString)) {
            queryParameters[decodeURIComponent(m[1])] = decodeURIComponent(m[2]);
        }


        var layout = queryParameters['layout'] ? queryParameters['layout'] : 'square';

        if (layout == 'square') {
            $('figure').css('height', '30%');
            $('figure').css('width', '30%');
        }

		
		
        var loader = $('#loader').html();
        $('#loader').remove();

        var instance = $(".imgrid").imgrid({
            gridLayout: layout,
            gridLoader: loader,
            gridAnimation: {
                trigger: 'onStart', //Suport onStart | onScroll
                animationType: 'shrink',
                animationDuration: 700,
                delay: true,    // Successively delay the animation of each element in a set by the targeted amount
                offsetTop: 150, // Distance in pixels from the lower edge of the window and the top edge of the row that must exist before running the animation..
                timeout: 0      // Wait a certain time before running the row animation.
            },
            
            gridColumns: 4,
            thumbMargin: 0,
            thumbHoverEffect: 'steve',
            thumbReziseImg: true,
			thumbLightbox: false
			
        });
		

        $('imgrid').on('imgrid.ready', function (e) {
            e.preventDefault();
            $('.imgrid').imgrid('resizeCaption', {maxFontSize: 4, widthToHide: 180})
        });

        $('#hover-effect').change(function () {
            queryParameters['hover-effect'] = $(this).val();
            location.search = $.param(queryParameters);
        });

        $('#layout option').each(function () {
            if ($(this).val() === queryParameters['layout']) {
                $(this).attr('selected', true);
            }
        });

        $('#layout').change(function () {
            queryParameters['layout'] = $(this).val();
            location.search = $.param(queryParameters);
        });

		
		
        $('.filter').click(function (e) {
            e.preventDefault();
            console.log($(this).data('filter'));
            $(".imgrid").imgrid('filter', $(this).data('filter'));
        });

		
		
		
		
	
        var more_id = 1;		
		
        $('#more').click(function (e) {
            e.preventDefault();
			
			

			
			
            if (more_id < 4) {
                $.get('more' + more_id + '.html', function (r) {
                    $(".imgrid").imgrid('addMore', r);
                });
            }
			
				
			
			
            more_id = more_id + 1;
			
            if (more_id > 3) {
                $(this).removeClass('orange').addClass('disabled').attr('data-tooltip', 'Nothing more to add...');
                console.log($(this).data('tooltip'))
                $('.tooltipped').tooltip({delay: 50});
            }

			
			$('.filter-numb3>div').replaceWith( '<div>Показано 28 работ из 28</div>');	
			
			$('.filter-numb3').removeClass('filter-numb3').addClass('filter-numb4');				
			
			
			
			
			$('.filter-numb2>div').replaceWith( '<div>Показано 24 работ из 28</div>');	
			
			$('.filter-numb2').removeClass('filter-numb2').addClass('filter-numb3');			
		
			
			
			
			$('.filter-numb1>div').replaceWith( '<div>Показано 20 работ из 28</div>');	
			
			$('.filter-numb1').removeClass('filter-numb1').addClass('filter-numb2');
			
			
			
			
			

			
        })
		
		

    });
	
			
		
	
		













	  
